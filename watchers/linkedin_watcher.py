"""
LinkedIn Watcher — Silver Tier

Monitors LinkedIn via Playwright for:
- New connection requests
- New direct messages
- Notifications (mentions, comments, reactions)
- New job opportunities (optional)

Creates action files in AI_Employee_Vault/Needs_Action/ for Claude to process.

Session is persisted at watchers/sessions/linkedin/ so login is only done once.

Usage:
    cd watchers
    python linkedin_watcher.py          # normal mode
    LOG_ONLY=true python linkedin_watcher.py  # dry-run (no vault writes)

First run:
    LINKEDIN_FIRST_LOGIN=true python linkedin_watcher.py
    # This opens a headed browser so you can log in manually.
    # After login, session is saved and future runs are headless.
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

# ── config ─────────────────────────────────────────────────────────────────────
SESSION_DIR = Path(__file__).parent / "sessions" / "linkedin"
PROCESSED_IDS_FILE = Path(__file__).parent / ".linkedin_processed_ids.json"
CHECK_INTERVAL = int(os.getenv("LINKEDIN_CHECK_INTERVAL", "300"))  # 5 minutes
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"
FIRST_LOGIN = os.getenv("LINKEDIN_FIRST_LOGIN", "false").lower() == "true"

LINKEDIN_EMAIL = os.getenv("LINKEDIN_EMAIL", "")
LINKEDIN_PASSWORD = os.getenv("LINKEDIN_PASSWORD", "")

# Keywords in messages that should be flagged as high priority
HIGH_PRIORITY_KEYWORDS = [
    "urgent", "asap", "invoice", "payment", "proposal", "contract",
    "hire", "opportunity", "offer", "partnership", "collaboration",
    "pricing", "quote", "demo", "call",
]


class LinkedInWatcher(BaseWatcher):
    """Monitors LinkedIn via Playwright and creates Needs_Action files."""

    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=CHECK_INTERVAL)
        self.processed_ids: set[str] = self._load_processed_ids()
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        if DRY_RUN:
            self.logger.warning("DRY RUN MODE — no files will be written to vault")

    # ── processed IDs ──────────────────────────────────────────────────────────

    def _load_processed_ids(self) -> set[str]:
        if PROCESSED_IDS_FILE.exists():
            try:
                data = json.loads(PROCESSED_IDS_FILE.read_text())
                ids = set(data.get("ids", []))
                self.logger.info(f"Loaded {len(ids)} previously processed LinkedIn IDs")
                return ids
            except Exception:
                pass
        return set()

    def _save_processed_ids(self):
        ids_list = list(self.processed_ids)[-2000:]
        PROCESSED_IDS_FILE.write_text(
            json.dumps({"ids": ids_list, "updated": datetime.now(timezone.utc).isoformat()},
                       indent=2)
        )

    # ── browser helpers ────────────────────────────────────────────────────────

    def _get_playwright(self):
        try:
            from playwright.sync_api import sync_playwright
            return sync_playwright
        except ImportError:
            self.logger.error(
                "Playwright not installed. Run: uv add playwright && playwright install chromium"
            )
            raise

    def _launch_browser(self, playwright):
        """Launch persistent browser context (reuses LinkedIn session)."""
        headless = not FIRST_LOGIN  # headed on first login so user can interact
        return playwright.chromium.launch_persistent_context(
            str(SESSION_DIR),
            headless=headless,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )

    def _is_logged_in(self, page) -> bool:
        """Return True if the current page shows a logged-in LinkedIn feed."""
        try:
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(2000)
            url = page.url.split("?")[0]  # strip query params to avoid false positives
            return url.rstrip("/").endswith("/feed") or "/mynetwork" in url
        except Exception:
            return False

    def _login(self, page):
        """Perform LinkedIn login (headless must be False for first login)."""
        if not LINKEDIN_EMAIL or not LINKEDIN_PASSWORD:
            self.logger.warning(
                "LINKEDIN_EMAIL / LINKEDIN_PASSWORD not set in .env. "
                "Starting browser for manual login. Close browser when done."
            )
            page.goto("https://www.linkedin.com/login")
            # Wait up to 5 minutes for manual login
            try:
                page.wait_for_url("**/feed/**", timeout=300_000)
                self.logger.info("Manual login successful")
            except Exception:
                self.logger.error("Login timeout — please retry")
            return

        page.goto("https://www.linkedin.com/login", wait_until="networkidle")
        page.fill('input[name="session_key"]', LINKEDIN_EMAIL)
        page.fill('input[name="session_password"]', LINKEDIN_PASSWORD)
        page.click('button[type="submit"]')

        try:
            page.wait_for_url("**/feed/**", timeout=30_000)
            self.logger.info(f"Logged in as {LINKEDIN_EMAIL}")
        except Exception:
            self.logger.warning(
                "Login may require 2FA or CAPTCHA — browser is open for manual completion."
            )
            page.wait_for_url("**/feed/**", timeout=120_000)

    # ── scrape functions ───────────────────────────────────────────────────────

    def _scrape_messages(self, page) -> list[dict]:
        """Scrape new direct messages from LinkedIn messaging."""
        items = []
        try:
            page.goto("https://www.linkedin.com/messaging/", wait_until="domcontentloaded",
                      timeout=15000)
            page.wait_for_timeout(2000)

            # Find conversation threads with unread indicators
            threads = page.query_selector_all(
                "[data-control-name='overlay.open_conversation_thread_item']"
            )
            if not threads:
                # Fallback selector
                threads = page.query_selector_all(".msg-conversation-listitem")

            for thread in threads[:10]:
                try:
                    # Check for unread badge
                    unread_badge = thread.query_selector(
                        ".notification-badge, [class*='unread']"
                    )
                    if not unread_badge:
                        continue

                    name_el = thread.query_selector(
                        ".msg-conversation-listitem__participant-names, "
                        "[class*='participant-name']"
                    )
                    snippet_el = thread.query_selector(
                        ".msg-conversation-listitem__message-snippet, "
                        "[class*='message-snippet']"
                    )
                    name = name_el.inner_text().strip() if name_el else "Unknown"
                    snippet = snippet_el.inner_text().strip() if snippet_el else ""

                    # Build a stable ID from name + snippet hash
                    item_id = f"msg_{hash(name + snippet) & 0xFFFFFFFF:08x}"

                    if item_id not in self.processed_ids:
                        items.append({
                            "id": item_id,
                            "type": "message",
                            "from": name,
                            "snippet": snippet,
                        })
                except Exception:
                    continue

        except Exception as e:
            self.logger.warning(f"Could not scrape messages: {e}")
        return items

    def _scrape_connections(self, page) -> list[dict]:
        """Scrape new connection requests."""
        items = []
        try:
            page.goto(
                "https://www.linkedin.com/mynetwork/invitation-manager/",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            page.wait_for_timeout(2000)

            # Each invitation card
            cards = page.query_selector_all(
                ".invitation-card, [class*='invitation-card']"
            )
            for card in cards[:10]:
                try:
                    name_el = card.query_selector(
                        ".invitation-card__title, [class*='person-name']"
                    )
                    title_el = card.query_selector(
                        ".invitation-card__subtitle, [class*='occupation']"
                    )
                    name = name_el.inner_text().strip() if name_el else "Unknown"
                    title = title_el.inner_text().strip() if title_el else ""

                    item_id = f"conn_{hash(name + title) & 0xFFFFFFFF:08x}"
                    if item_id not in self.processed_ids:
                        items.append({
                            "id": item_id,
                            "type": "connection_request",
                            "from": name,
                            "title": title,
                        })
                except Exception:
                    continue

        except Exception as e:
            self.logger.warning(f"Could not scrape connections: {e}")
        return items

    def _scrape_notifications(self, page) -> list[dict]:
        """Scrape recent LinkedIn notifications."""
        items = []
        try:
            page.goto(
                "https://www.linkedin.com/notifications/",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            page.wait_for_timeout(2000)

            notifs = page.query_selector_all(
                ".nt-card, [class*='notification-card'], "
                "[data-control-name='notification.click_notification_card']"
            )
            for notif in notifs[:10]:
                try:
                    # Skip already-read notifications
                    is_unread = notif.query_selector("[class*='unread'], .nt-card--unread")
                    if not is_unread:
                        continue

                    text_el = notif.query_selector(
                        ".nt-card__text, [class*='notification-text'], "
                        ".artdeco-entity-lockup__subtitle"
                    )
                    text = text_el.inner_text().strip() if text_el else notif.inner_text()[:200].strip()

                    item_id = f"notif_{hash(text) & 0xFFFFFFFF:08x}"
                    if item_id not in self.processed_ids:
                        items.append({
                            "id": item_id,
                            "type": "notification",
                            "text": text,
                        })
                except Exception:
                    continue

        except Exception as e:
            self.logger.warning(f"Could not scrape notifications: {e}")
        return items

    # ── core watcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """Open LinkedIn, scrape all new activity, return list of items."""
        sync_playwright = self._get_playwright()
        all_items = []

        with sync_playwright() as p:
            ctx = self._launch_browser(p)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()

                if not self._is_logged_in(page):
                    self.logger.info("Not logged in — running login flow...")
                    self._login(page)

                messages = self._scrape_messages(page)
                connections = self._scrape_connections(page)
                notifications = self._scrape_notifications(page)

                all_items = messages + connections + notifications
                self.logger.info(
                    f"LinkedIn: {len(messages)} msgs, {len(connections)} connections, "
                    f"{len(notifications)} notifications"
                )
            finally:
                ctx.close()

        return all_items

    def create_action_file(self, item: dict) -> Path:
        """Write a Needs_Action .md file for the given LinkedIn item."""
        item_type = item.get("type", "unknown")
        item_id = item.get("id", "unknown")
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

        priority = self._detect_priority(item)

        if item_type == "message":
            filename = f"LINKEDIN_MSG_{timestamp}.md"
            content = self._message_file(item, now, priority)
        elif item_type == "connection_request":
            filename = f"LINKEDIN_CONN_{timestamp}.md"
            content = self._connection_file(item, now, priority)
        else:
            filename = f"LINKEDIN_NOTIF_{timestamp}.md"
            content = self._notification_file(item, now, priority)

        filepath = self.needs_action / filename

        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would create: {filepath}")
        else:
            filepath.write_text(content, encoding="utf-8")
            self.logger.info(f"Created: {filename} [type={item_type}, priority={priority}]")

        self.processed_ids.add(item_id)
        self._save_processed_ids()

        self.log_action(
            action_type=f"linkedin_{item_type}_detected",
            target=item_id,
            result="success" if not DRY_RUN else "dry_run",
            details={**item, "priority": priority, "file": filename},
        )
        return filepath

    # ── file templates ─────────────────────────────────────────────────────────

    def _message_file(self, item: dict, now: datetime, priority: str) -> str:
        return f"""---
type: linkedin_message
source: linkedin
item_id: {item['id']}
from: {item.get('from', 'Unknown')}
received: {now.isoformat()}
priority: {priority}
status: pending
---

## LinkedIn Message from {item.get('from', 'Unknown')}

**Received:** {now.strftime('%Y-%m-%d %H:%M UTC')}
**Priority:** {priority.upper()}

### Message Preview

{item.get('snippet', '_No preview available_')}

---

## Suggested Actions

- [ ] Read full message on LinkedIn
- [ ] Draft reply (requires approval before sending)
- [ ] Add sender to Contacts if not already there
- [ ] Log in /Accounting if related to a client

---

_Source: LinkedIn Watcher_
"""

    def _connection_file(self, item: dict, now: datetime, priority: str) -> str:
        return f"""---
type: linkedin_connection_request
source: linkedin
item_id: {item['id']}
from: {item.get('from', 'Unknown')}
sender_title: {item.get('title', '')}
received: {now.isoformat()}
priority: {priority}
status: pending
---

## LinkedIn Connection Request from {item.get('from', 'Unknown')}

**Title:** {item.get('title', 'N/A')}
**Received:** {now.strftime('%Y-%m-%d %H:%M UTC')}

---

## Suggested Actions

- [ ] Review sender profile on LinkedIn
- [ ] Accept if relevant (client, partner, recruiter)
- [ ] Ignore/decline if spam
- [ ] If accepted: send welcome message (requires approval)

---

_Source: LinkedIn Watcher_
"""

    def _notification_file(self, item: dict, now: datetime, priority: str) -> str:
        return f"""---
type: linkedin_notification
source: linkedin
item_id: {item['id']}
received: {now.isoformat()}
priority: {priority}
status: pending
---

## LinkedIn Notification

**Received:** {now.strftime('%Y-%m-%d %H:%M UTC')}
**Priority:** {priority.upper()}

### Content

{item.get('text', '_No text available_')}

---

## Suggested Actions

- [ ] Review and categorise
- [ ] Reply or engage if appropriate (requires approval)
- [ ] Archive if informational only

---

_Source: LinkedIn Watcher_
"""

    def _detect_priority(self, item: dict) -> str:
        text = " ".join(str(v) for v in item.values()).lower()
        if any(kw in text for kw in HIGH_PRIORITY_KEYWORDS):
            return "high"
        return "normal"


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Load .env if present
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    vault_path = os.getenv(
        "VAULT_PATH",
        str(Path(__file__).parent.parent / "AI_Employee_Vault"),
    )
    watcher = LinkedInWatcher(vault_path)
    watcher.run()


if __name__ == "__main__":
    main()
