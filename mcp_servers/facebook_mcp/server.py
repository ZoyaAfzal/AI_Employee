"""
Facebook MCP Server — Gold Tier

Exposes Facebook Graph API capabilities to Claude Code via MCP tools.
Handles Facebook Pages and Instagram Business accounts.

Tools exposed:
  - fb_post_to_page       : post text/link to a Facebook Page
  - fb_get_page_posts     : get recent posts from a page
  - fb_get_page_insights  : get engagement metrics for a page
  - fb_post_to_instagram  : post image/caption to Instagram Business
  - fb_get_instagram_posts: get recent Instagram posts
  - fb_get_post_comments  : get comments on a post
  - fb_reply_to_comment   : reply to a comment (requires approval)
  - fb_generate_summary   : generate engagement summary report

Prerequisites:
  1. Facebook App with pages_manage_posts, pages_read_engagement permissions
  2. Long-lived Page Access Token
  3. pip install mcp requests

Environment vars (in .env):
  FB_PAGE_ID           — Facebook Page ID (numeric)
  FB_PAGE_ACCESS_TOKEN — Long-lived Page Access Token
  FB_INSTAGRAM_ID      — Instagram Business Account ID (optional)
  VAULT_PATH           — path to AI_Employee_Vault

Add to Claude Code settings:
{
  "mcpServers": {
    "facebook": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_servers/facebook_mcp/server.py"],
      "env": {
        "FB_PAGE_ID": "your_page_id",
        "FB_PAGE_ACCESS_TOKEN": "your_token",
        "VAULT_PATH": "/absolute/path/to/AI_Employee_Vault"
      }
    }
  }
}
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Any

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError:
    print("ERROR: mcp not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ── config ─────────────────────────────────────────────────────────────────────
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
FB_INSTAGRAM_ID = os.getenv("FB_INSTAGRAM_ID", "")
GRAPH_API_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

VAULT_PATH = Path(os.getenv("VAULT_PATH", Path(__file__).parent.parent.parent / "AI_Employee_Vault"))
LOGS_DIR = VAULT_PATH / "Logs"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [FacebookMCP] %(levelname)s: %(message)s")
logger = logging.getLogger("FacebookMCP")


# ── Facebook Graph API helpers ─────────────────────────────────────────────────

def _graph_get(path: str, params: dict = None) -> dict:
    params = params or {}
    params["access_token"] = FB_ACCESS_TOKEN
    resp = requests.get(f"{GRAPH_BASE}/{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _graph_post(path: str, data: dict) -> dict:
    data = dict(data)
    data["access_token"] = FB_ACCESS_TOKEN
    resp = requests.post(f"{GRAPH_BASE}/{path}", data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _require_credentials():
    if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
        raise RuntimeError(
            "Facebook credentials not configured. Set FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN in .env"
        )


def _log_action(action_type: str, details: dict, result: str = "success"):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{date.today().isoformat()}.json"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "facebook_mcp",
        "details": details,
        "result": result,
    }
    existing = []
    if log_file.exists():
        try:
            existing = json.loads(log_file.read_text())
        except Exception:
            existing = []
    existing.append(entry)
    log_file.write_text(json.dumps(existing, indent=2))


# ── MCP server ─────────────────────────────────────────────────────────────────

server = Server("facebook-mcp")


@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="fb_post_to_page",
            description="Post a text message or link to the configured Facebook Page. Requires prior approval for non-scheduled posts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Post text content"},
                    "link": {"type": "string", "description": "Optional URL to include"},
                    "scheduled_publish_time": {"type": "integer", "description": "Unix timestamp for scheduled post (optional)"},
                    "published": {"type": "boolean", "default": True},
                },
                "required": ["message"],
            },
        ),
        Tool(
            name="fb_get_page_posts",
            description="Get recent posts from the Facebook Page with engagement metrics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                    "include_insights": {"type": "boolean", "default": True},
                },
            },
        ),
        Tool(
            name="fb_get_page_insights",
            description="Get page-level insights: reach, impressions, fans, engagement.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {"type": "string", "enum": ["day", "week", "days_28", "month"], "default": "week"},
                    "metrics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["page_impressions", "page_engaged_users", "page_fan_adds", "page_post_engagements"],
                    },
                },
            },
        ),
        Tool(
            name="fb_post_to_instagram",
            description="Post an image with caption to Instagram Business account. Requires image URL (publicly accessible).",
            inputSchema={
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "description": "Public URL of the image to post"},
                    "caption": {"type": "string", "description": "Instagram caption with hashtags"},
                },
                "required": ["image_url", "caption"],
            },
        ),
        Tool(
            name="fb_get_instagram_posts",
            description="Get recent Instagram posts with engagement metrics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "default": 10},
                },
            },
        ),
        Tool(
            name="fb_get_post_comments",
            description="Get comments on a specific Facebook post.",
            inputSchema={
                "type": "object",
                "properties": {
                    "post_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["post_id"],
            },
        ),
        Tool(
            name="fb_reply_to_comment",
            description="Reply to a comment on a Facebook post. Requires approval file in /Approved/.",
            inputSchema={
                "type": "object",
                "properties": {
                    "comment_id": {"type": "string"},
                    "message": {"type": "string"},
                    "approval_file": {"type": "string", "description": "Path to approved file"},
                },
                "required": ["comment_id", "message", "approval_file"],
            },
        ),
        Tool(
            name="fb_generate_summary",
            description="Generate a weekly Facebook/Instagram engagement summary report and save to vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period_days": {"type": "integer", "default": 7},
                    "save_to_vault": {"type": "boolean", "default": True},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    try:
        result = await _dispatch(name, arguments)
        _log_action(name, arguments, "success")
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        _log_action(name, {**arguments, "error": str(e)}, "error")
        logger.error(f"Tool {name} failed: {e}")
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _dispatch(name: str, args: dict) -> Any:
    if name == "fb_post_to_page":
        return _post_to_page(args)
    elif name == "fb_get_page_posts":
        return _get_page_posts(args)
    elif name == "fb_get_page_insights":
        return _get_page_insights(args)
    elif name == "fb_post_to_instagram":
        return _post_to_instagram(args)
    elif name == "fb_get_instagram_posts":
        return _get_instagram_posts(args)
    elif name == "fb_get_post_comments":
        return _get_post_comments(args)
    elif name == "fb_reply_to_comment":
        return _reply_to_comment(args)
    elif name == "fb_generate_summary":
        return _generate_summary(args)
    else:
        raise ValueError(f"Unknown tool: {name}")


def _post_to_page(args: dict) -> dict:
    _require_credentials()
    if DRY_RUN:
        return {"dry_run": True, "message": "DRY RUN: post not published", "content": args.get("message", "")[:100]}

    payload = {"message": args["message"]}
    if args.get("link"):
        payload["link"] = args["link"]
    if args.get("scheduled_publish_time"):
        payload["scheduled_publish_time"] = args["scheduled_publish_time"]
        payload["published"] = False
    else:
        payload["published"] = args.get("published", True)

    result = _graph_post(f"{FB_PAGE_ID}/feed", payload)
    return {"success": True, "post_id": result.get("id"), "message_preview": args["message"][:100]}


def _get_page_posts(args: dict) -> dict:
    _require_credentials()
    limit = args.get("limit", 10)
    data = _graph_get(
        f"{FB_PAGE_ID}/posts",
        {
            "fields": "id,message,created_time,full_picture,permalink_url,likes.summary(true),comments.summary(true),shares",
            "limit": limit,
        },
    )
    posts = data.get("data", [])
    summary = []
    for post in posts:
        summary.append({
            "id": post.get("id"),
            "message": (post.get("message", "")[:100] + "...") if len(post.get("message", "")) > 100 else post.get("message", ""),
            "created_time": post.get("created_time"),
            "likes": post.get("likes", {}).get("summary", {}).get("total_count", 0),
            "comments": post.get("comments", {}).get("summary", {}).get("total_count", 0),
            "shares": post.get("shares", {}).get("count", 0),
            "url": post.get("permalink_url"),
        })
    return {"count": len(summary), "posts": summary}


def _get_page_insights(args: dict) -> dict:
    _require_credentials()
    metrics = args.get("metrics", ["page_impressions", "page_engaged_users", "page_fan_adds"])
    period = args.get("period", "week")
    data = _graph_get(
        f"{FB_PAGE_ID}/insights",
        {"metric": ",".join(metrics), "period": period},
    )
    results = {}
    for item in data.get("data", []):
        name = item.get("name")
        values = item.get("values", [])
        results[name] = values[-1].get("value", 0) if values else 0
    return {"period": period, "metrics": results}


def _post_to_instagram(args: dict) -> dict:
    _require_credentials()
    if not FB_INSTAGRAM_ID:
        return {"error": "FB_INSTAGRAM_ID not configured"}
    if DRY_RUN:
        return {"dry_run": True, "message": "DRY RUN: Instagram post not published"}

    # Step 1: create media container
    container = _graph_post(f"{FB_INSTAGRAM_ID}/media", {
        "image_url": args["image_url"],
        "caption": args["caption"],
    })
    creation_id = container.get("id")
    if not creation_id:
        return {"error": "Failed to create Instagram media container", "response": container}

    # Step 2: publish the container
    publish_result = _graph_post(f"{FB_INSTAGRAM_ID}/media_publish", {
        "creation_id": creation_id,
    })
    return {"success": True, "instagram_post_id": publish_result.get("id")}


def _get_instagram_posts(args: dict) -> dict:
    _require_credentials()
    if not FB_INSTAGRAM_ID:
        return {"error": "FB_INSTAGRAM_ID not configured"}
    limit = args.get("limit", 10)
    data = _graph_get(
        f"{FB_INSTAGRAM_ID}/media",
        {"fields": "id,caption,media_type,timestamp,like_count,comments_count,permalink", "limit": limit},
    )
    return {"count": len(data.get("data", [])), "posts": data.get("data", [])}


def _get_post_comments(args: dict) -> dict:
    _require_credentials()
    data = _graph_get(
        f"{args['post_id']}/comments",
        {"fields": "id,message,from,created_time", "limit": args.get("limit", 20)},
    )
    return {"count": len(data.get("data", [])), "comments": data.get("data", [])}


def _reply_to_comment(args: dict) -> dict:
    approval_file = Path(args.get("approval_file", ""))
    if not approval_file.exists():
        return {"error": f"Approval file not found: {approval_file}"}
    if DRY_RUN:
        return {"dry_run": True, "message": "DRY RUN: comment reply not sent"}

    result = _graph_post(f"{args['comment_id']}/comments", {"message": args["message"]})
    return {"success": True, "reply_id": result.get("id")}


def _generate_summary(args: dict) -> dict:
    _require_credentials()
    period_days = args.get("period_days", 7)
    period = "week" if period_days <= 7 else "days_28"

    # Get insights
    insights = _get_page_insights({"period": period, "metrics": [
        "page_impressions", "page_engaged_users", "page_fan_adds", "page_post_engagements"
    ]})

    # Get recent posts
    posts_data = _get_page_posts({"limit": 10})

    # Instagram if configured
    ig_posts = {}
    if FB_INSTAGRAM_ID:
        ig_posts = _get_instagram_posts({"limit": 5})

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": period_days,
        "facebook": {
            "page_insights": insights.get("metrics", {}),
            "recent_posts": posts_data.get("posts", [])[:5],
            "total_posts_analyzed": posts_data.get("count", 0),
        },
        "instagram": ig_posts,
    }

    if args.get("save_to_vault", True):
        VAULT_PATH.mkdir(parents=True, exist_ok=True)
        briefings_dir = VAULT_PATH / "Briefings"
        briefings_dir.mkdir(exist_ok=True)
        filename = f"{date.today().isoformat()}_Social_Media_Summary.md"
        content = _format_summary_md(summary)
        (briefings_dir / filename).write_text(content)
        summary["saved_to"] = str(briefings_dir / filename)

    return summary


def _format_summary_md(summary: dict) -> str:
    fb = summary.get("facebook", {})
    metrics = fb.get("page_insights", {})
    posts = fb.get("recent_posts", [])

    lines = [
        f"# Social Media Summary — {date.today().isoformat()}",
        "",
        f"*Generated: {summary['generated_at']}*",
        f"*Period: {summary['period_days']} days*",
        "",
        "## Facebook Page",
        "",
        "### Insights",
        f"- Impressions: {metrics.get('page_impressions', 'N/A')}",
        f"- Engaged Users: {metrics.get('page_engaged_users', 'N/A')}",
        f"- New Fans: {metrics.get('page_fan_adds', 'N/A')}",
        f"- Post Engagements: {metrics.get('page_post_engagements', 'N/A')}",
        "",
        "### Recent Posts",
    ]
    for post in posts[:5]:
        lines.append(f"- **{post.get('created_time', 'unknown')}**: {post.get('message', 'no text')}")
        lines.append(f"  - Likes: {post.get('likes', 0)}, Comments: {post.get('comments', 0)}, Shares: {post.get('shares', 0)}")

    ig = summary.get("instagram", {})
    if ig.get("posts"):
        lines.extend(["", "## Instagram", ""])
        for post in ig.get("posts", [])[:5]:
            lines.append(f"- **{post.get('timestamp', 'unknown')}**: {(post.get('caption','') or '')[:80]}")
            lines.append(f"  - Likes: {post.get('like_count', 0)}, Comments: {post.get('comments_count', 0)}")

    lines.extend(["", "---", "*Generated by AI Employee Gold Tier*"])
    return "\n".join(lines)


# ── entry point ────────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
