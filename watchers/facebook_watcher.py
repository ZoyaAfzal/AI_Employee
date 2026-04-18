"""
Facebook Watcher — Gold Tier

Monitors Facebook Page for:
- New comments on posts (keyword-triggered)
- New messages in Page inbox
- Significant engagement spikes
- Mentions of the page

Creates action files in AI_Employee_Vault/Needs_Action/ for Claude to process.

Usage:
    cd watchers
    python facebook_watcher.py

Environment vars (set in .env):
    FB_PAGE_ID           — Facebook Page ID
    FB_PAGE_ACCESS_TOKEN — Page Access Token
    FB_CHECK_INTERVAL    — polling interval in seconds (default: 300)
    VAULT_PATH           — path to AI_Employee_Vault
    LOG_ONLY             — true for dry-run
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

try:
    import requests
except ImportError:
    print("ERROR: requests not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

# ── config ─────────────────────────────────────────────────────────────────────
FB_PAGE_ID = os.getenv("FB_PAGE_ID", "")
FB_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN", "")
GRAPH_API_VERSION = "v19.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
CHECK_INTERVAL = int(os.getenv("FB_CHECK_INTERVAL", "300"))  # 5 minutes
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

PROCESSED_IDS_FILE = Path(__file__).parent / ".facebook_processed_ids.json"

COMMENT_KEYWORDS = [
    "price", "pricing", "how much", "cost", "interested", "buy", "purchase",
    "contact", "help", "support", "urgent", "invoice", "order",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [FacebookWatcher] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            str(Path(__file__).parent.parent / "logs" / "facebook_watcher.log"),
            mode="a",
        ),
    ],
)
logger = logging.getLogger("FacebookWatcher")


class FacebookWatcher(BaseWatcher):
    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=CHECK_INTERVAL)
        self.processed_ids = self._load_processed_ids()

    def _load_processed_ids(self) -> set:
        if PROCESSED_IDS_FILE.exists():
            try:
                return set(json.loads(PROCESSED_IDS_FILE.read_text()))
            except Exception:
                pass
        return set()

    def _save_processed_ids(self):
        ids_list = list(self.processed_ids)[-2000:]  # keep last 2000
        PROCESSED_IDS_FILE.write_text(json.dumps(ids_list))

    def _graph_get(self, path: str, params: dict = None) -> dict:
        params = params or {}
        params["access_token"] = FB_ACCESS_TOKEN
        resp = requests.get(f"{GRAPH_BASE}/{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def check_for_updates(self) -> list:
        if not FB_PAGE_ID or not FB_ACCESS_TOKEN:
            logger.warning("Facebook credentials not configured — skipping check")
            return []

        items = []
        items.extend(self._check_comments())
        items.extend(self._check_page_messages())
        return items

    def _check_comments(self) -> list:
        try:
            # Get recent posts
            posts_data = self._graph_get(
                f"{FB_PAGE_ID}/posts",
                {"fields": "id,message,created_time", "limit": 10},
            )
            posts = posts_data.get("data", [])
            new_items = []

            for post in posts:
                post_id = post.get("id")
                # Get comments on each post
                comments_data = self._graph_get(
                    f"{post_id}/comments",
                    {
                        "fields": "id,message,from,created_time",
                        "limit": 20,
                        "filter": "stream",
                    },
                )
                for comment in comments_data.get("data", []):
                    comment_id = comment.get("id")
                    if comment_id in self.processed_ids:
                        continue

                    message = comment.get("message", "").lower()
                    is_keyword_match = any(kw in message for kw in COMMENT_KEYWORDS)
                    comment_from = comment.get("from", {})

                    new_items.append({
                        "type": "fb_comment",
                        "comment_id": comment_id,
                        "post_id": post_id,
                        "post_message": (post.get("message", "") or "")[:100],
                        "comment_message": comment.get("message", ""),
                        "from_name": comment_from.get("name", "Unknown"),
                        "from_id": comment_from.get("id", ""),
                        "created_time": comment.get("created_time", ""),
                        "keyword_match": is_keyword_match,
                        "priority": "high" if is_keyword_match else "low",
                    })
                    self.processed_ids.add(comment_id)

            return new_items
        except Exception as e:
            logger.error(f"Error checking comments: {e}")
            return []

    def _check_page_messages(self) -> list:
        try:
            # Facebook Page Conversations
            convos_data = self._graph_get(
                f"{FB_PAGE_ID}/conversations",
                {"fields": "id,unread_count,updated_time,participants", "limit": 10},
            )
            new_items = []

            for convo in convos_data.get("data", []):
                if convo.get("unread_count", 0) == 0:
                    continue
                convo_id = convo.get("id")
                if convo_id in self.processed_ids:
                    continue

                # Get latest messages
                msgs_data = self._graph_get(
                    f"{convo_id}/messages",
                    {"fields": "id,message,from,created_time", "limit": 5},
                )
                latest_messages = msgs_data.get("data", [])
                if not latest_messages:
                    continue

                latest = latest_messages[0]
                new_items.append({
                    "type": "fb_message",
                    "conversation_id": convo_id,
                    "message_id": latest.get("id"),
                    "message": latest.get("message", ""),
                    "from_name": latest.get("from", {}).get("name", "Unknown"),
                    "created_time": latest.get("created_time", ""),
                    "unread_count": convo.get("unread_count", 1),
                    "priority": "high",
                })
                self.processed_ids.add(convo_id)

            return new_items
        except requests.HTTPError as e:
            if e.response.status_code == 200:
                return []
            logger.error(f"Error checking page messages: {e}")
            return []
        except Exception as e:
            logger.error(f"Error checking page messages: {e}")
            return []

    def create_action_file(self, item: dict) -> Path:
        item_type = item["type"]
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        priority = item.get("priority", "medium")

        if item_type == "fb_comment":
            filename = f"FACEBOOK_comment_{item['from_name'].replace(' ', '_')}_{timestamp}.md"
            content = f"""---
type: facebook_comment
source: facebook
priority: {priority}
from: {item['from_name']}
comment_id: {item['comment_id']}
post_id: {item['post_id']}
received: {timestamp}
keyword_match: {item['keyword_match']}
status: pending
---

## Facebook Comment

**From:** {item['from_name']}
**Post:** {item['post_message']}
**Comment:** {item['comment_message']}
**Time:** {item['created_time']}

## Context
{"⚠️ KEYWORD MATCH — potential sales/support inquiry" if item['keyword_match'] else "General comment"}

## Suggested Actions
- [ ] Review comment and decide if reply needed
- [ ] If sales inquiry → create approval request for reply
- [ ] If spam/irrelevant → archive
"""
        elif item_type == "fb_message":
            filename = f"FACEBOOK_message_{item['from_name'].replace(' ', '_')}_{timestamp}.md"
            content = f"""---
type: facebook_message
source: facebook
priority: high
from: {item['from_name']}
conversation_id: {item['conversation_id']}
received: {timestamp}
unread_count: {item['unread_count']}
status: pending
---

## Facebook Page Message

**From:** {item['from_name']}
**Message:** {item['message']}
**Unread in thread:** {item['unread_count']}
**Time:** {item['created_time']}

## Suggested Actions
- [ ] Draft reply (requires approval)
- [ ] Flag as lead if sales inquiry
- [ ] Archive if resolved
"""
        else:
            filename = f"FACEBOOK_event_{timestamp}.md"
            content = f"---\ntype: facebook_event\n---\n\n{json.dumps(item, indent=2)}\n"

        if DRY_RUN:
            logger.info(f"[DRY RUN] Would create: {filename}")
            return self.needs_action / filename

        filepath = self.needs_action / filename
        filepath.write_text(content)
        logger.info(f"Created action file: {filename} (priority: {priority})")
        return filepath

    def run(self):
        logger.info(f"Starting FacebookWatcher (page: {FB_PAGE_ID or 'NOT CONFIGURED'})")
        if not FB_PAGE_ID:
            logger.error("FB_PAGE_ID not set — FacebookWatcher cannot start. Set in .env")
            return
        super().run()

    def _after_batch(self, items):
        self._save_processed_ids()


if __name__ == "__main__":
    from pathlib import Path as _Path
    import dotenv
    env_file = _Path(__file__).parent.parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass

    vault = os.getenv("VAULT_PATH", str(_Path(__file__).parent.parent / "AI_Employee_Vault"))
    _Path(__file__).parent.parent.joinpath("logs").mkdir(parents=True, exist_ok=True)
    watcher = FacebookWatcher(vault)
    watcher.run()
