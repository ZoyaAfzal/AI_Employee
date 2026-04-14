"""
Gmail Watcher — Silver Tier

Monitors Gmail for new important/unread emails and creates action files
in AI_Employee_Vault/Needs_Action/ for Claude to process.

Features:
- Watches for unread emails matching configured filters (important, starred, labels)
- Extracts full metadata: sender, subject, snippet, thread ID, labels
- Detects priority signals: invoices, urgent keywords, client names
- De-duplicates via processed_ids set (persisted to disk between restarts)
- Graceful error handling: expired token, API rate limits, network failures
- Dry-run mode: LOG_ONLY=true env var prevents writing to vault

Usage:
    cd watchers
    python gmail_watcher.py              # normal mode
    LOG_ONLY=true python gmail_watcher.py  # dry-run
"""

import os
import sys
import json
import base64
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# ── path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher

# ── constants ──────────────────────────────────────────────────────────────────
CREDENTIALS_DIR = Path(__file__).parent / "credentials"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"
PROCESSED_IDS_FILE = Path(__file__).parent / ".gmail_processed_ids.json"

# Gmail query — change to taste
# "is:unread is:important"  → only Gmail-flagged important emails (narrow)
# "is:unread -category:promotions -category:social"  → all real emails, skip newsletters
# "is:unread"  → everything unread
GMAIL_QUERY = os.getenv("GMAIL_QUERY", "is:unread -category:promotions -category:social")
MAX_RESULTS = 20          # max emails to fetch per poll cycle
CHECK_INTERVAL = 120      # seconds between polls (2 minutes)

# Keywords that elevate priority to "high"
HIGH_PRIORITY_KEYWORDS = [
    "urgent", "asap", "invoice", "payment", "overdue", "deadline",
    "critical", "important", "action required", "please review",
    "contract", "proposal", "quote", "follow up",
]

DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"


class GmailWatcher(BaseWatcher):
    """Monitors Gmail and creates Needs_Action files for each new important email."""

    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=CHECK_INTERVAL)
        self.service = None
        self.sender_email = "unknown"
        self.processed_ids: set[str] = self._load_processed_ids()

        if DRY_RUN:
            self.logger.warning("DRY RUN MODE — no files will be written to vault")

    # ── Google API setup ───────────────────────────────────────────────────────

    def _build_service(self):
        """Build the Gmail API service, refreshing credentials if needed."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
        except ImportError:
            self.logger.error(
                "Missing Google libraries. Run: uv add google-auth google-auth-oauthlib "
                "google-auth-httplib2 google-api-python-client"
            )
            raise

        if not TOKEN_FILE.exists():
            raise FileNotFoundError(
                f"Gmail token not found at {TOKEN_FILE}. "
                "Run gmail_auth.py first to authorise."
            )

        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE))

        if creds.expired and creds.refresh_token:
            self.logger.info("Refreshing Gmail credentials...")
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json())

        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        self.sender_email = profile.get("emailAddress", "unknown")
        self.logger.info(f"Gmail connected as: {self.sender_email}")
        return service

    def _ensure_service(self):
        if self.service is None:
            self.service = self._build_service()
        return self.service

    # ── processed IDs persistence ──────────────────────────────────────────────

    def _load_processed_ids(self) -> set[str]:
        if PROCESSED_IDS_FILE.exists():
            try:
                data = json.loads(PROCESSED_IDS_FILE.read_text())
                ids = set(data.get("ids", []))
                self.logger.info(f"Loaded {len(ids)} previously processed Gmail IDs")
                return ids
            except Exception:
                pass
        return set()

    def _save_processed_ids(self):
        # Keep only the last 5 000 IDs to prevent unbounded growth
        ids_list = list(self.processed_ids)[-5000:]
        PROCESSED_IDS_FILE.write_text(
            json.dumps({"ids": ids_list, "updated": datetime.now(timezone.utc).isoformat()},
                       indent=2)
        )

    # ── core watcher interface ─────────────────────────────────────────────────

    def check_for_updates(self) -> list:
        """Return list of Gmail message dicts that haven't been processed yet."""
        try:
            svc = self._ensure_service()
            result = svc.users().messages().list(
                userId="me",
                q=GMAIL_QUERY,
                maxResults=MAX_RESULTS,
            ).execute()

            messages = result.get("messages", [])
            new_messages = [m for m in messages if m["id"] not in self.processed_ids]
            self.logger.info(
                f"Gmail poll: {len(messages)} matching, {len(new_messages)} new"
            )
            return new_messages


        except Exception as e:
            self.logger.error(f"Gmail API error: {e}")
            # Reset service so it's rebuilt on next poll (handles token expiry)
            self.service = None
            return []

    def create_action_file(self, message: dict) -> Path:
        """Fetch full message details and write a Needs_Action .md file."""
        msg_id = message["id"]

        try:
            svc = self._ensure_service()
            full_msg = svc.users().messages().get(
                userId="me",
                id=msg_id,
                format="full",
            ).execute()
        except Exception as e:
            self.logger.error(f"Failed to fetch message {msg_id}: {e}")
            self.processed_ids.add(msg_id)
            return Path()

        # ── parse headers ──────────────────────────────────────────────────────
        headers = {h["name"].lower(): h["value"]
                   for h in full_msg.get("payload", {}).get("headers", [])}

        sender = headers.get("from", "Unknown Sender")
        subject = headers.get("subject", "(No Subject)")
        date_str = headers.get("date", "")
        reply_to = headers.get("reply-to", sender)
        cc = headers.get("cc", "")

        # Parse date
        try:
            received_dt = parsedate_to_datetime(date_str)
            received = received_dt.isoformat()
        except Exception:
            received = datetime.now(timezone.utc).isoformat()

        # ── extract body snippet ───────────────────────────────────────────────
        snippet = full_msg.get("snippet", "")
        body_text = self._extract_body(full_msg.get("payload", {}))

        # ── priority detection ─────────────────────────────────────────────────
        combined_text = f"{subject} {snippet} {body_text}".lower()
        priority = self._detect_priority(combined_text)
        email_type = self._detect_type(combined_text)
        labels = full_msg.get("labelIds", [])
        thread_id = full_msg.get("threadId", "")

        # ── build filename ─────────────────────────────────────────────────────
        safe_subject = re.sub(r"[^\w\s-]", "", subject)[:40].strip().replace(" ", "_")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"EMAIL_{safe_subject}_{timestamp}.md"
        filepath = self.needs_action / filename

        # ── build suggested actions ────────────────────────────────────────────
        suggested_actions = self._build_suggested_actions(email_type, sender, subject)

        # ── write the action file ──────────────────────────────────────────────
        content = f"""---
type: email
source: gmail
message_id: {msg_id}
thread_id: {thread_id}
from: {sender}
reply_to: {reply_to}
cc: {cc}
subject: {subject}
received: {received}
priority: {priority}
email_type: {email_type}
labels: {json.dumps(labels)}
status: pending
---

## Email: {subject}

**From:** {sender}
**Received:** {received}
**Priority:** {priority.upper()}
**Type:** {email_type}

---

### Preview

{snippet}

---

### Full Body

{body_text[:2000] if body_text else "_Body not extractable — check Gmail directly._"}

---

## Suggested Actions

{suggested_actions}

---

_Source: Gmail Watcher | Message ID: {msg_id}_
"""
        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would create: {filepath}")
        else:
            filepath.write_text(content, encoding="utf-8")
            self.logger.info(f"Created action file: {filename} [priority={priority}]")

        # Mark as processed and persist
        self.processed_ids.add(msg_id)
        self._save_processed_ids()

        # Mark email as read in Gmail so it doesn't re-appear
        try:
            self._ensure_service().users().messages().modify(
                userId="me",
                id=msg_id,
                body={"removeLabelIds": ["UNREAD"]},
            ).execute()
        except Exception:
            pass  # non-fatal

        self.log_action(
            action_type="email_detected",
            target=msg_id,
            result="success" if not DRY_RUN else "dry_run",
            details={
                "from": sender,
                "subject": subject,
                "priority": priority,
                "email_type": email_type,
                "file": filename,
            },
        )
        return filepath

    # ── helpers ────────────────────────────────────────────────────────────────

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text body from Gmail payload."""
        mime = payload.get("mimeType", "")

        if mime == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

        # Multipart: recurse into parts
        for part in payload.get("parts", []):
            text = self._extract_body(part)
            if text:
                return text

        return ""

    def _detect_priority(self, text: str) -> str:
        if any(kw in text for kw in HIGH_PRIORITY_KEYWORDS):
            return "high"
        return "normal"

    def _detect_type(self, text: str) -> str:
        if any(kw in text for kw in ["invoice", "payment", "receipt", "billing"]):
            return "finance"
        if any(kw in text for kw in ["proposal", "quote", "contract", "agreement"]):
            return "business"
        if any(kw in text for kw in ["meeting", "call", "schedule", "calendar", "appointment"]):
            return "meeting"
        if any(kw in text for kw in ["unsubscribe", "newsletter", "promotion"]):
            return "newsletter"
        return "general"

    def _build_suggested_actions(self, email_type: str, sender: str, subject: str) -> str:
        actions = {
            "finance": (
                "- [ ] Review invoice/payment details\n"
                "- [ ] Check against Accounting records\n"
                "- [ ] Approve or flag for human review\n"
                "- [ ] Reply with acknowledgement (requires approval)"
            ),
            "business": (
                "- [ ] Read full proposal/contract\n"
                "- [ ] Summarise key terms in Dashboard\n"
                "- [ ] Draft reply (requires approval before sending)\n"
                "- [ ] Add deadline to Plans/"
            ),
            "meeting": (
                "- [ ] Check calendar availability\n"
                "- [ ] Draft meeting confirmation reply\n"
                "- [ ] Create calendar event (requires approval)"
            ),
            "newsletter": (
                "- [ ] Scan for relevant business insights\n"
                "- [ ] Archive or unsubscribe"
            ),
        }
        return actions.get(
            email_type,
            (
                "- [ ] Read and categorise\n"
                "- [ ] Draft reply if needed (requires approval)\n"
                "- [ ] Archive after processing"
            ),
        )


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    vault_path = os.getenv(
        "VAULT_PATH",
        str(Path(__file__).parent.parent / "AI_Employee_Vault"),
    )
    watcher = GmailWatcher(vault_path)
    watcher.run()


if __name__ == "__main__":
    main()
