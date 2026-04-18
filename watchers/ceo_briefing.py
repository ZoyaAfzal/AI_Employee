"""
CEO Briefing Generator — Gold Tier

Generates the Monday Morning CEO Briefing by:
1. Reading Odoo accounting data (via JSON-RPC)
2. Reading vault task stats (/Done, /Pending_Approval)
3. Reading Facebook/social media summaries
4. Summarizing with Claude Code
5. Writing briefing to /Vault/Briefings/

Run manually or via weekly cron:
    cd watchers && python ceo_briefing.py

Or via orchestrator schedule (runs every Sunday night).

Environment vars:
    ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD
    VAULT_PATH
    CLAUDE_PATH — path to claude binary (default: claude)
"""

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone, date, timedelta

# ── config ─────────────────────────────────────────────────────────────────────
VAULT_PATH = Path(os.getenv("VAULT_PATH", Path(__file__).parent.parent / "AI_Employee_Vault"))
ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USERNAME", "admin")
ODOO_PASS = os.getenv("ODOO_PASSWORD", "admin")
CLAUDE_PATH = os.getenv("CLAUDE_PATH", "claude")
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [CEOBriefing] %(levelname)s: %(message)s",
)
logger = logging.getLogger("CEOBriefing")


# ── Odoo data fetcher ──────────────────────────────────────────────────────────

def _odoo_rpc(endpoint: str, params: dict) -> dict:
    try:
        import requests
        payload = {"jsonrpc": "2.0", "method": "call", "id": 1, "params": params}
        session = requests.Session()
        session.post(f"{ODOO_URL}/web/session/authenticate", json={
            "jsonrpc": "2.0", "method": "call", "id": 1,
            "params": {"db": ODOO_DB, "login": ODOO_USER, "password": ODOO_PASS},
        }, timeout=10)
        resp = session.post(f"{ODOO_URL}{endpoint}", json=payload, timeout=30)
        data = resp.json()
        if "error" in data:
            return {}
        return data.get("result", {})
    except Exception as e:
        logger.warning(f"Odoo RPC failed: {e}")
        return {}


def get_odoo_accounting_summary() -> dict:
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    if today.month == 12:
        month_end = f"{today.year + 1}-01-01"
    else:
        month_end = f"{today.year}-{today.month + 1:02d}-01"

    # Revenue
    invoices = _odoo_rpc("/web/dataset/call_kw", {
        "model": "account.move",
        "method": "search_read",
        "args": [[
            ["move_type", "=", "out_invoice"],
            ["invoice_date", ">=", month_start],
            ["invoice_date", "<", month_end],
        ]],
        "kwargs": {
            "fields": ["name", "partner_id", "amount_total", "amount_residual", "payment_state"],
            "limit": 100,
        },
    })

    # Expenses
    bills = _odoo_rpc("/web/dataset/call_kw", {
        "model": "account.move",
        "method": "search_read",
        "args": [[
            ["move_type", "=", "in_invoice"],
            ["invoice_date", ">=", month_start],
            ["invoice_date", "<", month_end],
        ]],
        "kwargs": {"fields": ["name", "amount_total"], "limit": 100},
    })

    if isinstance(invoices, list):
        total_invoiced = sum(r.get("amount_total", 0) for r in invoices)
        total_paid = sum(r.get("amount_total", 0) - r.get("amount_residual", 0) for r in invoices)
        total_outstanding = sum(r.get("amount_residual", 0) for r in invoices)
    else:
        total_invoiced = total_paid = total_outstanding = 0
        invoices = []

    total_expenses = sum(r.get("amount_total", 0) for r in (bills if isinstance(bills, list) else []))

    return {
        "month": today.strftime("%B %Y"),
        "total_invoiced": total_invoiced,
        "total_paid": total_paid,
        "total_outstanding": total_outstanding,
        "invoice_count": len(invoices) if isinstance(invoices, list) else 0,
        "total_expenses": total_expenses,
        "net_profit": total_paid - total_expenses,
    }


# ── Vault stats ────────────────────────────────────────────────────────────────

def get_vault_stats() -> dict:
    done_dir = VAULT_PATH / "Done"
    pending_dir = VAULT_PATH / "Pending_Approval"
    inbox_dir = VAULT_PATH / "Inbox"
    needs_action_dir = VAULT_PATH / "Needs_Action"

    # Count done files this week
    one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    done_this_week = 0
    if done_dir.exists():
        for f in done_dir.rglob("*.md"):
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
                if mtime >= one_week_ago:
                    done_this_week += 1
            except Exception:
                pass

    return {
        "tasks_done_this_week": done_this_week,
        "pending_approvals": len(list(pending_dir.glob("*.md"))) if pending_dir.exists() else 0,
        "inbox_count": len(list(inbox_dir.glob("*"))) if inbox_dir.exists() else 0,
        "needs_action_count": len(list(needs_action_dir.glob("*.md"))) if needs_action_dir.exists() else 0,
    }


# ── Social media summary ───────────────────────────────────────────────────────

def get_social_summary() -> dict:
    briefings_dir = VAULT_PATH / "Briefings"
    if not briefings_dir.exists():
        return {}

    # Find the most recent social media summary
    summaries = sorted(briefings_dir.glob("*Social_Media_Summary.md"), reverse=True)
    if not summaries:
        return {"message": "No social media summary available yet"}

    latest = summaries[0]
    try:
        content = latest.read_text()
        return {"source_file": latest.name, "content_preview": content[:500]}
    except Exception:
        return {}


# ── Briefing generator ─────────────────────────────────────────────────────────

def generate_briefing() -> Path:
    today = date.today()
    logger.info("Generating CEO Briefing...")

    accounting = get_odoo_accounting_summary()
    vault_stats = get_vault_stats()
    social = get_social_summary()

    # Load business goals if available
    goals_file = VAULT_PATH / "Business_Goals.md"
    goals_content = goals_file.read_text() if goals_file.exists() else "Business Goals not yet configured."

    # Build the briefing data context
    context = {
        "date": today.isoformat(),
        "accounting": accounting,
        "vault_stats": vault_stats,
        "social_summary": social,
    }

    # Use Claude to generate narrative if available, else use template
    briefing_content = _generate_with_claude(context, goals_content)

    # Save briefing
    briefings_dir = VAULT_PATH / "Briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    weekday = today.strftime("%A")
    briefing_file = briefings_dir / f"{today.isoformat()}_{weekday}_CEO_Briefing.md"

    if not DRY_RUN:
        briefing_file.write_text(briefing_content)
        logger.info(f"CEO Briefing saved: {briefing_file}")
    else:
        logger.info(f"[DRY RUN] Would save briefing to {briefing_file}")

    # Update dashboard
    _update_dashboard(briefing_file.name, today)

    return briefing_file


def _generate_with_claude(context: dict, goals: str) -> str:
    prompt = f"""Generate a Monday Morning CEO Briefing for the AI Employee system.

Use this data:

## Accounting Data (Odoo)
{json.dumps(context['accounting'], indent=2)}

## Task Stats (Vault)
{json.dumps(context['vault_stats'], indent=2)}

## Social Media Summary
{json.dumps(context['social_summary'], indent=2)}

## Business Goals
{goals[:2000]}

Format the briefing as a professional Markdown report with:
1. Executive Summary (2-3 sentences)
2. Revenue section with Odoo numbers
3. Tasks Completed This Week
4. Pending Items needing attention
5. Social Media Performance
6. Proactive Suggestions (2-3 actionable items)
7. Upcoming priorities

Use the CEO Briefing template from Company Handbook. Be concise and actionable.
Output the briefing date as {context['date']}.
"""

    try:
        result = subprocess.run(
            [CLAUDE_PATH, "--print", "--no-conversation", prompt],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        logger.warning(f"Claude returned non-zero or empty output: {result.stderr[:200]}")
    except Exception as e:
        logger.warning(f"Claude generation failed: {e}, using template fallback")

    return _template_briefing(context)


def _template_briefing(context: dict) -> str:
    acc = context["accounting"]
    stats = context["vault_stats"]
    today_str = context["date"]

    return f"""---
generated: {datetime.now(timezone.utc).isoformat()}
period: {today_str}
type: ceo_briefing
---

# Monday Morning CEO Briefing — {today_str}

*Generated by AI Employee Gold Tier*

## Executive Summary
Weekly operations summary. Revenue {'on track' if acc.get('total_paid', 0) > 0 else 'needs attention'}.
{stats.get('tasks_done_this_week', 0)} tasks completed this week with {stats.get('pending_approvals', 0)} pending approvals.

## Revenue ({acc.get('month', 'This Month')})
| Metric | Amount |
|--------|--------|
| Total Invoiced | ${acc.get('total_invoiced', 0):,.2f} |
| Total Paid | ${acc.get('total_paid', 0):,.2f} |
| Outstanding | ${acc.get('total_outstanding', 0):,.2f} |
| Total Expenses | ${acc.get('total_expenses', 0):,.2f} |
| **Net Profit** | **${acc.get('net_profit', 0):,.2f}** |

*Invoices this month: {acc.get('invoice_count', 0)}*

## Task Summary
- Tasks completed this week: **{stats.get('tasks_done_this_week', 0)}**
- Pending approvals: **{stats.get('pending_approvals', 0)}**
- Inbox items: {stats.get('inbox_count', 0)}
- Needs action: {stats.get('needs_action_count', 0)}

## Social Media
{context.get('social_summary', {}).get('content_preview', 'No recent social media data available.')}

## Proactive Suggestions
- [ ] Review {stats.get('pending_approvals', 0)} pending approval(s) in /Pending_Approval
- [ ] {'Collect outstanding invoices ($' + f"{acc.get('total_outstanding', 0):,.2f})" if acc.get('total_outstanding', 0) > 0 else 'All invoices paid — great!'}
- [ ] Review Facebook/Instagram engagement and plan next week posts

---
*AI Employee Gold Tier — CEO Briefing Auto-Generated*
"""


def _update_dashboard(briefing_filename: str, today: date):
    dashboard = VAULT_PATH / "Dashboard.md"
    if not dashboard.exists():
        return
    try:
        content = dashboard.read_text()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        new_activity = f"| {timestamp} | Generated CEO Briefing: {briefing_filename} | Complete |\n"

        if "## Recent Activity" in content:
            marker = "## Recent Activity\n| Timestamp | Action | Status |\n|-----------|--------|--------|\n"
            content = content.replace(marker, marker + new_activity)
        if not DRY_RUN:
            dashboard.write_text(content)
    except Exception as e:
        logger.warning(f"Dashboard update failed: {e}")


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
        except ImportError:
            pass
    Path(__file__).parent.parent.joinpath("logs").mkdir(parents=True, exist_ok=True)
    briefing_path = generate_briefing()
    print(f"CEO Briefing generated: {briefing_path}")
