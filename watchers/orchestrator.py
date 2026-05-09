"""
Orchestrator — AI Employee (MCP Edition)

Central coordinator. Tasks split into two cost tiers:

  ZERO COST — deterministic actions via direct MCP tool calls
    • Email send / reply after human approval   → Gmail MCP
    • File move, vault log, dashboard update    → Vault MCP

  SUBSCRIPTION (Claude Code CLI) — reasoning tasks
    • Process Needs_Action items                → claude --print
    • Daily / weekly briefings                  → claude --print
    • Handle rejections, generic approvals      → claude --print
    Claude Code uses vault+gmail MCP tools internally.

Architecture:
  ┌─────────────────────────────────────────────────────┐
  │  Orchestrator (this file)                           │
  │  ├── WatcherThreads  (FileSystem, Gmail, LinkedIn)  │
  │  ├── ApprovalMonitor — polls /Approved + /Rejected  │
  │  │     email/payment → direct MCP (zero cost)       │
  │  │     complex/generic → Claude Code CLI            │
  │  └── ScheduledTasks → Claude Code CLI (subscription)│
  └─────────────────────────────────────────────────────┘

Environment variables (set in .env):
    VAULT_PATH     — path to AI_Employee_Vault (default: ../AI_Employee_Vault)
    CLAUDE_PATH    — claude binary path (default: claude)
    ENABLE_GMAIL        — true/false (default: true)
    ENABLE_LINKEDIN     — true/false (default: true)
    ENABLE_FILESYSTEM   — true/false (default: true)
    LOG_ONLY            — true/false dry-run mode
"""

import os
import sys
import json
import signal
import logging
import threading
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

# ── path setup ─────────────────────────────────────────────────────────────────
WATCHERS_DIR = Path(__file__).parent
sys.path.insert(0, str(WATCHERS_DIR))

# ── config ─────────────────────────────────────────────────────────────────────
VAULT_PATH = Path(
    os.getenv("VAULT_PATH", str(WATCHERS_DIR.parent / "AI_Employee_Vault"))
)
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

ENABLE_GMAIL = os.getenv("ENABLE_GMAIL", "true").lower() == "true"
ENABLE_LINKEDIN = os.getenv("ENABLE_LINKEDIN", "true").lower() == "true"
ENABLE_FILESYSTEM = os.getenv("ENABLE_FILESYSTEM", "true").lower() == "true"
# Gold Tier
ENABLE_FACEBOOK = os.getenv("ENABLE_FACEBOOK", "true").lower() == "true"

APPROVAL_POLL_INTERVAL = 30   # seconds — how often to check /Approved and /Rejected
SCHEDULE_POLL_INTERVAL = 60   # seconds — how often to check scheduled tasks

# Ensure log directory exists
(WATCHERS_DIR.parent / "logs").mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(str(WATCHERS_DIR.parent / "logs" / "orchestrator.log"), mode="a"),
    ],
)
logger = logging.getLogger("Orchestrator")


# ── schedule state ─────────────────────────────────────────────────────────────

class ScheduleState:
    """Tracks last-run times for scheduled tasks, persisted to disk."""

    STATE_FILE = WATCHERS_DIR.parent / "logs" / "schedule_state.json"

    def __init__(self):
        self.state: dict = self._load()

    def _load(self) -> dict:
        if self.STATE_FILE.exists():
            try:
                return json.loads(self.STATE_FILE.read_text())
            except Exception:
                pass
        return {}

    def _save(self):
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.STATE_FILE.write_text(json.dumps(self.state, indent=2))

    def get_last_run(self, task_name: str) -> datetime | None:
        ts = self.state.get(task_name)
        if ts:
            try:
                return datetime.fromisoformat(ts)
            except Exception:
                pass
        return None

    def mark_ran(self, task_name: str):
        self.state[task_name] = datetime.now(timezone.utc).isoformat()
        self._save()

    def should_run(self, task_name: str, interval: timedelta) -> bool:
        last = self.get_last_run(task_name)
        if last is None:
            return True
        return datetime.now(timezone.utc) - last >= interval


# ── watcher thread management ──────────────────────────────────────────────────

class WatcherThread:
    """Runs a watcher class in a daemon thread with auto-restart."""

    def __init__(self, name: str, watcher_class, vault_path: str):
        self.name = name
        self.watcher_class = watcher_class
        self.vault_path = vault_path
        self.thread: threading.Thread | None = None
        self.running = False
        self._stop_event = threading.Event()

    def start(self):
        self.running = True
        self.thread = threading.Thread(
            target=self._run_with_restart, name=self.name, daemon=True
        )
        self.thread.start()
        logger.info(f"Started watcher thread: {self.name}")

    def stop(self):
        self.running = False
        self._stop_event.set()

    def is_alive(self) -> bool:
        return self.thread is not None and self.thread.is_alive()

    def _run_with_restart(self):
        while self.running and not self._stop_event.is_set():
            try:
                logger.info(f"{self.name}: starting watcher instance")
                watcher = self.watcher_class(self.vault_path)
                watcher.run()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"{self.name} crashed: {e}. Restarting in 30 seconds...")
                time.sleep(30)
        logger.info(f"{self.name}: stopped")


# ── direct Gmail / vault helpers (no MCP, no subprocess) ──────────────────────

def _send_gmail_direct(to: str, subject: str, body: str,
                       thread_id: str = "", in_reply_to: str = "") -> bool:
    """
    Send an email via Gmail API directly.
    Uses the same token.json the GmailWatcher uses — no MCP server needed.
    """
    import base64
    from email.mime.text import MIMEText

    token_path = WATCHERS_DIR / "credentials" / "token.json"
    if not token_path.exists():
        logger.error(f"Gmail token not found at {token_path}. Run gmail_auth.py first.")
        return False

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        logger.error("Google libraries missing. Run: uv add google-auth google-api-python-client")
        return False

    try:
        creds = Credentials.from_authorized_user_file(str(token_path))
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_path.write_text(creds.to_json())

        service = build("gmail", "v1", credentials=creds)

        mime = MIMEText(body, "plain", "utf-8")
        mime["to"] = to
        mime["subject"] = subject
        if in_reply_to:
            mime["In-Reply-To"] = in_reply_to
            mime["References"] = in_reply_to

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        send_body: dict = {"raw": raw}
        if thread_id:
            send_body["threadId"] = thread_id

        result = service.users().messages().send(userId="me", body=send_body).execute()
        logger.info(f"Email sent → {to} | subject: {subject!r} | id: {result.get('id')}")
        return True

    except Exception as e:
        logger.error(f"Gmail send failed: {e}")
        return False


def _vault_log(action_type: str, target: str, result: str, details: dict | None = None):
    """Append an entry to today's vault log JSON directly."""
    logs_dir = VAULT_PATH / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "orchestrator",
        "target": target,
        "result": result,
        "details": details or {},
    }
    entries: list = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except Exception:
            entries = []
    entries.append(entry)
    try:
        log_file.write_text(json.dumps(entries, indent=2))
    except Exception as e:
        logger.error(f"Could not write vault log: {e}")


def _dashboard_append(line: str):
    """Append a line to the Recent Activity section of Dashboard.md directly."""
    dashboard = VAULT_PATH / "Dashboard.md"
    if not dashboard.exists():
        return
    try:
        text = dashboard.read_text(encoding="utf-8")
        if "## Recent Activity" in text:
            text = text.replace(
                "## Recent Activity",
                f"## Recent Activity\n{line}",
                1,
            )
        else:
            text += f"\n## Recent Activity\n{line}\n"
        dashboard.write_text(text, encoding="utf-8")
    except Exception as e:
        logger.error(f"Could not update Dashboard.md: {e}")


# ── approval monitor ───────────────────────────────────────────────────────────

class ApprovalMonitor:
    """
    Polls /Approved and /Rejected folders every APPROVAL_POLL_INTERVAL seconds.

    Deterministic actions (email send, file moves, logging) go directly
    through MCP tool calls — no Claude subprocess needed.
    Complex actions (generic approvals, rejections with notes) delegate
    to the AgentRunner.
    """

    def __init__(self):
        self.approved_dir = VAULT_PATH / "Approved"
        self.rejected_dir = VAULT_PATH / "Rejected"
        self.processed: set[str] = set()

    def check(self):
        self._process_approved()
        self._process_rejected()

    # ── approved ──────────────────────────────────────────────────────────────

    def _process_approved(self):
        if not self.approved_dir.exists():
            return
        for f in sorted(self.approved_dir.glob("*.md")):
            if f.name in self.processed:
                continue
            logger.info(f"Approved action detected: {f.name}")
            self.processed.add(f.name)

            if f.name.startswith("EMAIL_"):
                self._handle_email_approval(f)
            elif f.name.startswith("LINKEDIN_"):
                self._handle_linkedin_approval(f)
            elif f.name.startswith("FACEBOOK_"):
                self._handle_facebook_approval(f)
            elif f.name.startswith("ODOO_"):
                self._handle_odoo_approval(f)
            elif f.name.startswith("PAYMENT_"):
                self._handle_payment_approval(f)
            else:
                self._handle_generic_approval(f)

    def _handle_email_approval(self, approval_file: Path):
        """
        Send the email described in the approval file.
        Reads the file directly (no MCP) and sends via Gmail API directly.
        """
        # Read the file directly — no MCP subprocess needed
        try:
            content = approval_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Could not read approval file {approval_file}: {e}")
            return

        email_fields = _parse_email_approval(content)
        if not email_fields or not email_fields.get("to") or not email_fields.get("body"):
            logger.warning(
                f"Could not parse email fields from {approval_file.name} "
                f"(got: {list(email_fields.keys()) if email_fields else 'none'}) — using agent"
            )
            self._handle_generic_approval(approval_file)
            return

        sent = _send_gmail_direct(
            to=email_fields["to"],
            subject=email_fields.get("subject", ""),
            body=email_fields["body"],
            thread_id=email_fields.get("thread_id", ""),
            in_reply_to=email_fields.get("message_id", ""),
        )

        if sent:
            # Move approval file to Done
            done_dir = VAULT_PATH / "Done"
            done_dir.mkdir(parents=True, exist_ok=True)
            try:
                approval_file.rename(done_dir / approval_file.name)
                logger.info(f"Approval file moved to Done: {approval_file.name}")
            except Exception as e:
                logger.error(f"Could not move approval file to Done: {e}")

            _vault_log(
                action_type="email_send",
                target=email_fields["to"],
                result="success",
                details={"subject": email_fields.get("subject", ""), "approval_file": approval_file.name},
            )
            _dashboard_append(
                f"| {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
                f"| Email sent: {email_fields.get('subject','')} → {email_fields['to']} | Complete |"
            )
        else:
            logger.error(f"Email send failed for {approval_file.name} — file left in Approved/ for retry")

    def _handle_linkedin_approval(self, approval_file: Path):
        """Delegate LinkedIn posting to the agent (requires browser automation)."""
        from agent_runner import run_agent_task
        vault = str(VAULT_PATH)
        run_agent_task(
            prompt=(
                f"Use the linkedin-poster skill to post the content from "
                f"{vault}\\Approved\\{approval_file.name} to LinkedIn.\n"
                f"After posting, move the file to {vault}\\Done\\ and update {vault}\\Dashboard.md"
            ),
            task_name=f"linkedin_{approval_file.stem}",
        )

    def _handle_facebook_approval(self, approval_file: Path):
        """Delegate Facebook/Instagram posting to the agent."""
        from agent_runner import run_agent_task
        vault = str(VAULT_PATH)
        run_agent_task(
            prompt=(
                f"Use the facebook-poster skill to post the content from "
                f"{vault}\\Approved\\{approval_file.name} to Facebook/Instagram.\n"
                f"After posting, move the file to {vault}\\Done\\ and update {vault}\\Dashboard.md"
            ),
            task_name=f"facebook_{approval_file.stem}",
        )

    def _handle_odoo_approval(self, approval_file: Path):
        """Execute approved Odoo actions (post invoices, etc.)."""
        from agent_runner import run_agent_task
        vault = str(VAULT_PATH)
        run_agent_task(
            prompt=(
                f"An Odoo action was approved. Read {vault}\\Approved\\{approval_file.name}\n"
                "Use the odoo-integration skill to execute the approved action.\n"
                "Common actions: post invoice (odoo_post_invoice), create customer, etc.\n"
                f"After completion, move the file to {vault}\\Done\\ and update {vault}\\Dashboard.md"
            ),
            task_name=f"odoo_{approval_file.stem}",
        )

    def _handle_payment_approval(self, approval_file: Path):
        """Payments are never auto-executed — note in dashboard and log."""
        logger.warning(f"Payment approval found: {approval_file.name} — manual action required")
        # Write directly — no MCP needed for simple file append
        dashboard = VAULT_PATH / "Dashboard.md"
        note = (
            f"\n- PAYMENT requires manual processing: `{approval_file.name}` "
            f"— received {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        try:
            with open(dashboard, "a", encoding="utf-8") as f:
                f.write(note)
        except Exception as e:
            logger.error(f"Could not update dashboard for payment: {e}")

    def _handle_generic_approval(self, approval_file: Path):
        """Unknown approval type — let the agent figure out what to do."""
        from agent_runner import run_agent_task
        vault = str(VAULT_PATH)
        run_agent_task(
            prompt=(
                f"A human-approved action is waiting: read {vault}\\Approved\\{approval_file.name}\n"
                "Understand what was approved, execute the action, then:\n"
                f"- Move the approval file to {vault}\\Done\\\n"
                f"- Update {vault}\\Dashboard.md with the outcome."
            ),
            task_name=f"generic_approval_{approval_file.stem}",
        )

    # ── rejected ──────────────────────────────────────────────────────────────

    def _process_rejected(self):
        if not self.rejected_dir.exists():
            return
        for f in sorted(self.rejected_dir.glob("*.md")):
            if f.name in self.processed:
                continue
            logger.info(f"Rejected action: {f.name}")
            self.processed.add(f.name)
            self._handle_rejection(f)

    def _handle_rejection(self, rejection_file: Path):
        from agent_runner import run_agent_task
        vault = str(VAULT_PATH)
        run_agent_task(
            prompt=(
                f"An action was rejected by the human. Read {vault}\\Rejected\\{rejection_file.name}\n"
                "Check for a rejection reason in the file comments, then:\n"
                f"- Move the file to {vault}\\Done\\\n"
                f"- Update {vault}\\Dashboard.md with a rejection note.\n"
                "- If the task is still needed, create a new file in "
                f"  {vault}\\Needs_Action\\ explaining what was rejected and what to do next."
            ),
            task_name=f"rejected_{rejection_file.stem}",
        )


# ── scheduled tasks ────────────────────────────────────────────────────────────

def run_process_needs_action(schedule: ScheduleState, force: bool = False):
    """
    Process pending items in Needs_Action.

    Called immediately when new items arrive (force=True) or on the
    5-minute periodic fallback schedule.
    """
    if not force and not schedule.should_run("process_needs_action", timedelta(minutes=5)):
        return

    needs_action_dir = VAULT_PATH / "Needs_Action"
    if not needs_action_dir.exists():
        return
    pending = [f for f in needs_action_dir.glob("*.md") if not f.name.startswith(".")]
    if not pending:
        return

    from agent_runner import run_agent_task
    pending_names = ", ".join(f.name for f in pending[:5])
    logger.info(f"Processing {len(pending)} item(s) in Needs_Action (force={force}): {pending_names}")
    vault = str(VAULT_PATH)
    success = run_agent_task(
        prompt=(
            f"You are the AI Employee. Process all pending items in {vault}\\Needs_Action\\\n\n"
            f"Files waiting: {', '.join(f.name for f in pending)}\n\n"
            "For each file:\n"
            f"1. Read the file from {vault}\\Needs_Action\\<filename>\n"
            f"2. Read {vault}\\Company_Handbook.md to check approval thresholds.\n"
            "3. Decide what action is needed:\n"
            "   - EMAIL items: does it need a reply? If yes, create an approval request.\n"
            "   - FILE items: categorise and process per handbook.\n"
            "   - INVOICE items: always create an approval request.\n"
            "4. For items needing approval:\n"
            f"   Create a file in {vault}\\Pending_Approval\\ with this format:\n"
            "   ---\n"
            "   type: approval_request\n"
            "   action: send_email  (or process_invoice etc)\n"
            "   to: <recipient if email>\n"
            "   subject: <subject>\n"
            "   status: pending\n"
            "   ---\n"
            "   ## What the AI Wants to Do\n"
            "   <clear description>\n"
            "   ## Email Preview\n"
            "   ---\n"
            "   <full email body>\n"
            "   ---\n"
            "   ## To Approve\n"
            f"   Move this file to {vault}\\Approved\\\n"
            "   ## To Reject\n"
            f"   Move this file to {vault}\\Rejected\\\n\n"
            f"5. Update {vault}\\Dashboard.md with current status.\n"
            f"6. Move processed Needs_Action files to {vault}\\Done\\ when complete."
        ),
        task_name="process_needs_action",
    )
    if success:
        schedule.mark_ran("process_needs_action")


def run_daily_briefing(schedule: ScheduleState):
    """Generate daily briefing at 8 AM local time."""
    now = datetime.now()
    if now.hour != 8:
        return
    if not schedule.should_run("daily_briefing", timedelta(hours=23)):
        return

    from agent_runner import run_agent_task
    today = now.strftime("%Y-%m-%d")
    vault = str(VAULT_PATH)
    result = run_agent_task(
        prompt=(
            "Generate today's daily briefing for the AI Employee.\n\n"
            f"1. List files in {vault}\\Needs_Action\\ and {vault}\\Pending_Approval\\\n"
            f"2. Read {vault}\\Dashboard.md for current status.\n"
            f"3. Write the briefing to {vault}\\Briefings\\DAILY_{today}.md\n"
            "   Include: pending tasks, items awaiting approval, recent completions.\n"
            f"4. Update {vault}\\Dashboard.md System Status section with today's summary."
        ),
        task_name="daily_briefing",
    )
    if result is not None:
        schedule.mark_ran("daily_briefing")


def run_weekly_ceo_briefing(schedule: ScheduleState):
    """Generate Monday morning CEO briefing using ceo_briefing.py (Gold Tier)."""
    now = datetime.now()
    if now.weekday() != 0 or now.hour != 7:
        return
    if not schedule.should_run("weekly_ceo_briefing", timedelta(days=6)):
        return

    # Gold Tier: use the dedicated ceo_briefing.py script (includes Odoo data)
    try:
        import subprocess
        result = subprocess.run(
            ["python3", str(WATCHERS_DIR / "ceo_briefing.py")],
            capture_output=True, text=True, timeout=300,
            cwd=str(WATCHERS_DIR),
        )
        if result.returncode == 0:
            logger.info(f"CEO Briefing (Gold): {result.stdout.strip()}")
            schedule.mark_ran("weekly_ceo_briefing")
            return
        logger.warning(f"ceo_briefing.py failed ({result.returncode}): {result.stderr[:200]} — falling back to agent")
    except Exception as e:
        logger.warning(f"ceo_briefing.py error: {e} — falling back to agent")

    from agent_runner import run_agent_task
    today = now.strftime("%Y-%m-%d")
    vault = str(VAULT_PATH)
    result = run_agent_task(
        prompt=(
            "Generate the Monday Morning CEO Briefing using the ceo-briefing skill.\n\n"
            f"1. Use odoo_get_accounting_summary to get this month's revenue data.\n"
            f"2. Count completed tasks in {vault}\\Done\\ (files modified in last 7 days).\n"
            f"3. Read {vault}\\Business_Goals.md if it exists.\n"
            f"4. Get social media summary via fb_generate_summary tool.\n"
            f"5. Write the briefing to {vault}\\Briefings\\{today}_Monday_CEO_Briefing.md\n"
            "   Sections: Executive Summary, Revenue (from Odoo), Tasks, Social Media, Suggestions.\n"
            f"6. Update {vault}\\Dashboard.md with a briefing summary."
        ),
        task_name="weekly_ceo_briefing",
    )
    if result is not None:
        schedule.mark_ran("weekly_ceo_briefing")


def run_linkedin_posting(schedule: ScheduleState):
    """Post to LinkedIn on Tue/Thu at 9 AM if an approved post exists."""
    now = datetime.now()
    if now.weekday() not in (1, 3) or now.hour != 9:
        return
    if not schedule.should_run("linkedin_post", timedelta(hours=23)):
        return

    approved_dir = VAULT_PATH / "Approved"
    approved_posts = list(approved_dir.glob("LINKEDIN_*.md")) if approved_dir.exists() else []
    if not approved_posts:
        logger.info("No approved LinkedIn posts found for scheduled posting")
        return

    from agent_runner import run_agent_task
    vault = str(VAULT_PATH)
    result = run_agent_task(
        prompt=(
            "Use the linkedin-poster skill to post all approved LinkedIn content.\n"
            f"1. Read each LINKEDIN_*.md file in {vault}\\Approved\\\n"
            "2. Post to LinkedIn using the linkedin-poster skill.\n"
            f"3. Move each posted file from {vault}\\Approved\\ to {vault}\\Done\\\n"
            f"4. Update {vault}\\Dashboard.md to note the activity."
        ),
        task_name="linkedin_post",
    )
    if result is not None:
        schedule.mark_ran("linkedin_post")


# ── Gold Tier scheduled tasks ──────────────────────────────────────────────────

def run_facebook_posting(schedule: ScheduleState):
    """Post to Facebook on Mon/Wed/Fri at 10 AM if an approved post exists."""
    now = datetime.now()
    if now.weekday() not in (0, 2, 4) or now.hour != 10:
        return
    if not schedule.should_run("facebook_post", timedelta(hours=23)):
        return

    approved_dir = VAULT_PATH / "Approved"
    approved_posts = list(approved_dir.glob("FACEBOOK_*.md")) if approved_dir.exists() else []
    if not approved_posts:
        logger.info("No approved Facebook posts found for scheduled posting")
        return

    from agent_runner import run_agent_task
    vault = str(VAULT_PATH)
    result = run_agent_task(
        prompt=(
            "Use the facebook-poster skill to post all approved Facebook content.\n"
            f"1. Read each FACEBOOK_*.md file in {vault}\\Approved\\\n"
            "2. Post to the Facebook Page using the facebook-poster skill (fb_post_to_page tool).\n"
            "3. If an Instagram post is indicated, also post to Instagram.\n"
            f"4. Move each posted file from {vault}\\Approved\\ to {vault}\\Done\\\n"
            f"5. Update {vault}\\Dashboard.md to note the activity."
        ),
        task_name="facebook_post",
    )
    if result is not None:
        schedule.mark_ran("facebook_post")


def run_social_media_summary(schedule: ScheduleState):
    """Generate a weekly social media summary every Sunday at 7 PM."""
    now = datetime.now()
    if now.weekday() != 6 or now.hour != 19:
        return
    if not schedule.should_run("social_media_summary", timedelta(days=6)):
        return

    from agent_runner import run_agent_task
    vault = str(VAULT_PATH)
    result = run_agent_task(
        prompt=(
            "Use the facebook-poster skill to generate a weekly social media summary.\n"
            "Call the fb_generate_summary tool with period_days=7 and save_to_vault=true.\n"
            f"Save the report to {vault}\\Briefings\\\n"
            f"Update {vault}\\Dashboard.md with the social media stats."
        ),
        task_name="social_media_summary",
    )
    if result is not None:
        schedule.mark_ran("social_media_summary")


def run_weekly_odoo_audit(schedule: ScheduleState):
    """Run weekly Odoo accounting audit every Sunday at 8 PM."""
    now = datetime.now()
    if now.weekday() != 6 or now.hour != 20:
        return
    if not schedule.should_run("weekly_odoo_audit", timedelta(days=6)):
        return

    try:
        import subprocess
        result = subprocess.run(
            ["python3", str(WATCHERS_DIR / "ceo_briefing.py")],
            capture_output=True, text=True, timeout=300,
            cwd=str(WATCHERS_DIR),
        )
        if result.returncode == 0:
            logger.info(f"CEO Briefing generated: {result.stdout.strip()}")
            schedule.mark_ran("weekly_odoo_audit")
        else:
            logger.error(f"CEO Briefing failed: {result.stderr[:500]}")
    except Exception as e:
        logger.error(f"Weekly Odoo audit failed: {e}")


# ── email approval file parser ─────────────────────────────────────────────────

def _parse_email_approval(content: str) -> dict | None:
    """
    Extract email fields from an approval file.

    Handles multiple formats Claude might use when writing approval files:
      - YAML frontmatter keys  (to: ..., subject: ..., thread_id: ...)
      - Markdown bold labels   (**To:** ..., **Subject:** ...)
      - Bullet list values     (- Message ID: ..., - Thread ID: ...)
      - Email Preview block    (body between ## Email Preview / --- markers)

    Returns None if at minimum a recipient can't be found.
    """
    import re

    fields: dict = {}

    # ── 1. YAML frontmatter ────────────────────────────────────────────────────
    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---", content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, _, v = line.partition(":")
                key = k.strip().lower().replace(" ", "_").replace("-", "_")
                val = v.strip()
                if val:
                    fields[key] = val

    # ── 2. Scan every line for common label patterns ───────────────────────────
    LABEL_MAP = {
        "to":         ("to:", "**to:**"),
        "subject":    ("subject:", "**subject:**"),
        "thread_id":  ("thread_id:", "thread id:", "- thread id:"),
        "message_id": ("message_id:", "message id:", "- message id:", "- message id:"),
    }
    for line in content.splitlines():
        stripped = line.strip().rstrip("*")
        lower = stripped.lower()
        for field, prefixes in LABEL_MAP.items():
            if field in fields:
                continue
            for prefix in prefixes:
                if lower.startswith(prefix):
                    val = stripped[len(prefix):].strip().strip("*").strip()
                    if val:
                        fields[field] = val
                    break

    # ── 3. Body: extract between ## Email Preview / --- markers ───────────────
    if "body" not in fields:
        body_match = re.search(
            r"##\s*Email Preview[^\n]*\n---+\r?\n(.*?)(?:\n---+|\Z)",
            content, re.DOTALL,
        )
        if body_match:
            raw_body = body_match.group(1).strip()
            # Strip leading To: / Subject: / Cc: header lines
            body_lines = raw_body.splitlines()
            skip_prefixes = ("to:", "subject:", "cc:", "bcc:", "from:")
            start = 0
            for i, ln in enumerate(body_lines):
                if ln.strip().lower().startswith(skip_prefixes):
                    start = i + 1
                elif ln.strip() == "":
                    if start == i:
                        start = i + 1  # skip blank line after headers
                    else:
                        break
                else:
                    break
            fields["body"] = "\n".join(body_lines[start:]).strip()

    # ── 4. Require at minimum a recipient ─────────────────────────────────────
    if not fields.get("to"):
        return None

    return fields


# ── main orchestrator ──────────────────────────────────────────────────────────

class Orchestrator:
    def __init__(self):
        self.watcher_threads: list[WatcherThread] = []
        self.approval_monitor = ApprovalMonitor()
        self.schedule = ScheduleState()
        self._shutdown = threading.Event()

        # Track known Needs_Action files so we can detect new arrivals
        self._known_needs_action: set[str] = self._snapshot_needs_action()
        # Set to True by _check_new_needs_action when new files arrive
        self._needs_action_dirty = threading.Event()

        self._check_claude_bin()

    def _check_claude_bin(self):
        """Warn early if the claude binary is not on PATH."""
        import shutil
        from agent_runner import CLAUDE_BIN
        if shutil.which(CLAUDE_BIN) is None:
            logger.warning(
                f"Claude binary not found on PATH: '{CLAUDE_BIN}'. "
                "Reasoning tasks will fail until CLAUDE_PATH is set in .env"
            )
        else:
            logger.info(f"Claude binary found: {CLAUDE_BIN}")

    def _snapshot_needs_action(self) -> set[str]:
        """Return the current set of filenames in Needs_Action/."""
        d = VAULT_PATH / "Needs_Action"
        if not d.exists():
            return set()
        return {f.name for f in d.glob("*.md") if not f.name.startswith(".")}

    def _check_new_needs_action(self) -> bool:
        """
        Compare Needs_Action/ against the last known snapshot.
        Returns True and sets the dirty flag if new files appeared.
        """
        current = self._snapshot_needs_action()
        new_files = current - self._known_needs_action
        self._known_needs_action = current
        if new_files:
            logger.info(f"New Needs_Action item(s): {', '.join(sorted(new_files))}")
            self._needs_action_dirty.set()
            return True
        return False

    def start_watchers(self):
        if ENABLE_FILESYSTEM:
            from filesystem_watcher import FileSystemWatcher
            t = WatcherThread("FileSystemWatcher", FileSystemWatcher, str(VAULT_PATH))
            self.watcher_threads.append(t)
            t.start()

        if ENABLE_GMAIL:
            try:
                from gmail_watcher import GmailWatcher
                t = WatcherThread("GmailWatcher", GmailWatcher, str(VAULT_PATH))
                self.watcher_threads.append(t)
                t.start()
            except ImportError:
                logger.warning("gmail_watcher.py not found — skipping Gmail watcher")
            except Exception as e:
                logger.warning(f"Could not start GmailWatcher: {e}")

        if ENABLE_LINKEDIN:
            try:
                from linkedin_watcher import LinkedInWatcher
                t = WatcherThread("LinkedInWatcher", LinkedInWatcher, str(VAULT_PATH))
                self.watcher_threads.append(t)
                t.start()
            except ImportError:
                logger.warning("linkedin_watcher.py not found — skipping LinkedIn watcher")
            except Exception as e:
                logger.warning(f"Could not start LinkedInWatcher: {e}")

        # Gold Tier: Facebook watcher
        if ENABLE_FACEBOOK:
            try:
                from facebook_watcher import FacebookWatcher
                t = WatcherThread("FacebookWatcher", FacebookWatcher, str(VAULT_PATH))
                self.watcher_threads.append(t)
                t.start()
            except ImportError:
                logger.warning("facebook_watcher.py not found — skipping Facebook watcher")
            except Exception as e:
                logger.warning(f"Could not start FacebookWatcher: {e}")

    def run_scheduled_tasks(self):
        run_daily_briefing(self.schedule)
        run_weekly_ceo_briefing(self.schedule)
        run_linkedin_posting(self.schedule)
        run_facebook_posting(self.schedule)        # Gold Tier
        run_social_media_summary(self.schedule)    # Gold Tier
        run_weekly_odoo_audit(self.schedule)       # Gold Tier
        run_process_needs_action(self.schedule)    # periodic fallback (5-min)

    def watchdog(self):
        for wt in self.watcher_threads:
            if wt.running and not wt.is_alive():
                logger.warning(f"Watcher {wt.name} died — restarting...")
                wt.start()

    def run(self):
        logger.info("=" * 60)
        logger.info("AI Employee Orchestrator (MCP Edition) starting")
        logger.info(f"Vault:    {VAULT_PATH}")
        logger.info(f"Gmail:    {ENABLE_GMAIL} | LinkedIn: {ENABLE_LINKEDIN} | FS: {ENABLE_FILESYSTEM}")
        logger.info(f"Dry-run:  {DRY_RUN}")
        logger.info("=" * 60)

        self.start_watchers()

        # Process anything already sitting in Needs_Action at startup
        startup_pending = self._snapshot_needs_action()
        if startup_pending:
            logger.info(f"Found {len(startup_pending)} existing item(s) in Needs_Action — processing now")
            run_process_needs_action(self.schedule, force=True)

        last_approval_check = 0.0
        last_schedule_check = 0.0

        while not self._shutdown.is_set():
            now = time.time()

            # ── check for new Needs_Action items every 5s ──────────────────
            self._check_new_needs_action()
            if self._needs_action_dirty.is_set():
                self._needs_action_dirty.clear()
                run_process_needs_action(self.schedule, force=True)

            # ── approval folder poll (every 30s) ───────────────────────────
            if now - last_approval_check >= APPROVAL_POLL_INTERVAL:
                self.approval_monitor.check()
                self.watchdog()
                last_approval_check = now

            # ── scheduled tasks fallback (every 60s) ──────────────────────
            if now - last_schedule_check >= SCHEDULE_POLL_INTERVAL:
                self.run_scheduled_tasks()
                last_schedule_check = now

            time.sleep(5)

        logger.info("Orchestrator shutting down...")
        for wt in self.watcher_threads:
            wt.stop()

    def shutdown(self, *_):
        logger.info("Shutdown signal received")
        self._shutdown.set()


def main():
    env_file = WATCHERS_DIR.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    orch = Orchestrator()
    signal.signal(signal.SIGINT, orch.shutdown)
    signal.signal(signal.SIGTERM, orch.shutdown)
    orch.run()


if __name__ == "__main__":
    main()
