"""
Gmail MCP Server — Silver Tier

Exposes Gmail capabilities to Claude Code as MCP tools:
  - send_email      : send an email (requires pre-approval)
  - draft_email     : save to Gmail Drafts (no approval needed)
  - search_emails   : search inbox
  - get_email       : fetch a specific message by ID
  - list_unread     : list unread important emails
  - reply_email     : reply to a thread

Add to ~/.claude.json (or Claude Code MCP settings):
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_servers/gmail_mcp/server.py"],
      "env": {
        "VAULT_PATH": "/absolute/path/to/AI_Employee_Vault",
        "GMAIL_TOKEN_PATH": "/absolute/path/to/watchers/credentials/token.json"
      }
    }
  }
}

Prerequisites:
    pip install mcp google-auth google-auth-httplib2 google-api-python-client
    Run watchers/gmail_auth.py first to generate the token.
"""

import os
import sys
import json
import base64
import logging
from pathlib import Path
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── MCP SDK ────────────────────────────────────────────────────────────────────
try:
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.types import Tool, TextContent, CallToolResult
except ImportError:
    print(
        "ERROR: mcp package not installed.\n"
        "Run: pip install mcp\n"
        "Or:  uv add mcp",
        file=sys.stderr,
    )
    sys.exit(1)

# ── config ─────────────────────────────────────────────────────────────────────
VAULT_PATH = Path(os.getenv("VAULT_PATH", Path(__file__).parent.parent.parent / "AI_Employee_Vault"))
TOKEN_PATH = Path(
    os.getenv(
        "GMAIL_TOKEN_PATH",
        Path(__file__).parent.parent.parent / "watchers" / "credentials" / "token.json",
    )
)
LOGS_DIR = VAULT_PATH / "Logs"
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [GmailMCP] %(levelname)s: %(message)s")
logger = logging.getLogger("GmailMCP")

# ── Gmail service helper ───────────────────────────────────────────────────────

def _get_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    if not TOKEN_PATH.exists():
        raise FileNotFoundError(
            f"Gmail token not found at {TOKEN_PATH}. Run watchers/gmail_auth.py first."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _log_action(action: str, target: str, result: str, details: dict | None = None):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action,
        "actor": "gmail_mcp",
        "target": target,
        "result": result,
        "details": details or {},
    }
    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except Exception:
            entries = []
    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2))


# ── MCP Server ─────────────────────────────────────────────────────────────────

server = Server("gmail-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="send_email",
            description=(
                "Send an email via Gmail. "
                "IMPORTANT: Only call this after human approval has been recorded "
                "in AI_Employee_Vault/Approved/. Always check approval-workflow skill first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Plain text email body"},
                    "cc": {"type": "string", "description": "CC addresses (comma separated)", "default": ""},
                    "approval_file": {
                        "type": "string",
                        "description": "Name of the approval file in /Approved/ confirming this send",
                    },
                },
                "required": ["to", "subject", "body", "approval_file"],
            },
        ),
        Tool(
            name="draft_email",
            description="Save an email as a Gmail Draft (does NOT send — no approval required).",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Plain text email body"},
                    "cc": {"type": "string", "description": "CC addresses (optional)", "default": ""},
                },
                "required": ["to", "subject", "body"],
            },
        ),
        Tool(
            name="search_emails",
            description="Search Gmail inbox using a Gmail query string.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Gmail search query, e.g. 'from:client@example.com is:unread', "
                            "'subject:invoice', 'after:2026/01/01 has:attachment'"
                        ),
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default 10, max 50)",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_email",
            description="Fetch the full content of a specific email by message ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID"},
                },
                "required": ["message_id"],
            },
        ),
        Tool(
            name="list_unread",
            description="List the most recent unread important emails.",
            inputSchema={
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Number of emails to list (default 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="reply_email",
            description=(
                "Reply to an existing Gmail thread. "
                "Requires approval_file for sends to external contacts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {"type": "string", "description": "Gmail thread ID"},
                    "message_id": {"type": "string", "description": "Message ID to reply to"},
                    "body": {"type": "string", "description": "Reply body text"},
                    "approval_file": {
                        "type": "string",
                        "description": "Approval file name (required for external contacts)",
                        "default": "",
                    },
                },
                "required": ["thread_id", "message_id", "body"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    try:
        if name == "send_email":
            return await _send_email(**arguments)
        elif name == "draft_email":
            return await _draft_email(**arguments)
        elif name == "search_emails":
            return await _search_emails(**arguments)
        elif name == "get_email":
            return await _get_email(**arguments)
        elif name == "list_unread":
            return await _list_unread(**arguments)
        elif name == "reply_email":
            return await _reply_email(**arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )
    except Exception as e:
        logger.error(f"Tool {name} error: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )


# ── tool implementations ───────────────────────────────────────────────────────

async def _send_email(to: str, subject: str, body: str,
                      approval_file: str, cc: str = "") -> CallToolResult:
    # Verify the approval file exists in /Approved/
    approval_path = VAULT_PATH / "Approved" / approval_file
    if not approval_path.exists():
        msg = (
            f"BLOCKED: Approval file not found: {approval_file}\n"
            f"Expected location: {approval_path}\n"
            "Create an approval request with the approval-workflow skill first."
        )
        _log_action("email_send_blocked", to, "blocked",
                    {"reason": "no_approval_file", "approval_file": approval_file})
        return CallToolResult(
            content=[TextContent(type="text", text=msg)], isError=True
        )

    if DRY_RUN:
        msg = f"[DRY RUN] Would send email to {to}: {subject}"
        _log_action("email_send", to, "dry_run", {"subject": subject, "to": to})
        return CallToolResult(content=[TextContent(type="text", text=msg)])

    svc = _get_service()
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    if cc:
        mime["cc"] = cc

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    result = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    msg_id = result.get("id", "unknown")

    # Move approval file to Done
    done_path = VAULT_PATH / "Done" / approval_file
    approval_path.rename(done_path)

    _log_action("email_send", to, "success",
                {"subject": subject, "to": to, "message_id": msg_id,
                 "approval_file": approval_file})

    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"✓ Email sent successfully.\nTo: {to}\nSubject: {subject}\nMessage ID: {msg_id}",
        )]
    )


async def _draft_email(to: str, subject: str, body: str, cc: str = "") -> CallToolResult:
    svc = _get_service()
    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    if cc:
        mime["cc"] = cc

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    result = svc.users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    draft_id = result.get("id", "unknown")

    _log_action("email_draft", to, "success",
                {"subject": subject, "to": to, "draft_id": draft_id})

    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"✓ Draft saved.\nTo: {to}\nSubject: {subject}\nDraft ID: {draft_id}",
        )]
    )


async def _search_emails(query: str, max_results: int = 10) -> CallToolResult:
    max_results = min(max_results, 50)
    svc = _get_service()

    result = svc.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    messages = result.get("messages", [])

    if not messages:
        return CallToolResult(
            content=[TextContent(type="text", text=f"No emails found for query: {query}")]
        )

    summaries = []
    for m in messages[:max_results]:
        try:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            summaries.append(
                f"ID: {m['id']}\n"
                f"  From: {headers.get('From', 'N/A')}\n"
                f"  Subject: {headers.get('Subject', 'N/A')}\n"
                f"  Date: {headers.get('Date', 'N/A')}\n"
                f"  Snippet: {msg.get('snippet', '')[:100]}"
            )
        except Exception:
            summaries.append(f"ID: {m['id']} — (failed to fetch details)")

    text = f"Found {len(messages)} email(s) for query '{query}':\n\n" + "\n\n".join(summaries)
    return CallToolResult(content=[TextContent(type="text", text=text)])


async def _get_email(message_id: str) -> CallToolResult:
    svc = _get_service()
    msg = svc.users().messages().get(
        userId="me", id=message_id, format="full"
    ).execute()

    headers = {h["name"]: h["value"]
               for h in msg.get("payload", {}).get("headers", [])}

    # Extract body
    body_text = _extract_body(msg.get("payload", {}))

    text = (
        f"Message ID: {message_id}\n"
        f"From: {headers.get('From', 'N/A')}\n"
        f"To: {headers.get('To', 'N/A')}\n"
        f"Subject: {headers.get('Subject', 'N/A')}\n"
        f"Date: {headers.get('Date', 'N/A')}\n"
        f"Labels: {', '.join(msg.get('labelIds', []))}\n\n"
        f"--- Body ---\n{body_text[:4000] if body_text else msg.get('snippet', '')}"
    )
    return CallToolResult(content=[TextContent(type="text", text=text)])


async def _list_unread(max_results: int = 10) -> CallToolResult:
    return await _search_emails("is:unread is:important", max_results)


async def _reply_email(thread_id: str, message_id: str,
                       body: str, approval_file: str = "") -> CallToolResult:
    # Fetch original to get subject + sender
    svc = _get_service()
    original = svc.users().messages().get(
        userId="me", id=message_id, format="metadata",
        metadataHeaders=["From", "Subject", "Message-ID"],
    ).execute()
    headers = {h["name"]: h["value"]
               for h in original.get("payload", {}).get("headers", [])}

    to = headers.get("From", "")
    subject = headers.get("Subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    orig_msg_id = headers.get("Message-ID", "")

    # Check approval if sending to external contact
    if approval_file:
        approval_path = VAULT_PATH / "Approved" / approval_file
        if not approval_path.exists():
            return CallToolResult(
                content=[TextContent(
                    type="text",
                    text=f"BLOCKED: Approval file not found: {approval_file}",
                )],
                isError=True,
            )

    if DRY_RUN:
        _log_action("email_reply", to, "dry_run", {"subject": subject, "thread_id": thread_id})
        return CallToolResult(
            content=[TextContent(type="text", text=f"[DRY RUN] Would reply to {to}: {subject}")]
        )

    mime = MIMEText(body)
    mime["to"] = to
    mime["subject"] = subject
    if orig_msg_id:
        mime["In-Reply-To"] = orig_msg_id
        mime["References"] = orig_msg_id

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    result = svc.users().messages().send(
        userId="me",
        body={"raw": raw, "threadId": thread_id},
    ).execute()

    if approval_file:
        (VAULT_PATH / "Approved" / approval_file).rename(
            VAULT_PATH / "Done" / approval_file
        )

    _log_action("email_reply", to, "success",
                {"subject": subject, "thread_id": thread_id,
                 "message_id": result.get("id")})

    return CallToolResult(
        content=[TextContent(
            type="text",
            text=f"✓ Reply sent.\nTo: {to}\nSubject: {subject}",
        )]
    )


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""


# ── entry point ────────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
