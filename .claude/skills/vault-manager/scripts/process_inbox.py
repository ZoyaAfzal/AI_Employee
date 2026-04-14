"""Process items in Needs_Action and update the Dashboard."""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone


def get_vault_path() -> Path:
    """Get the vault path."""
    vault = Path(__file__).parent.parent.parent.parent.parent / "AI_Employee_Vault"
    if len(sys.argv) > 1:
        vault = Path(sys.argv[1])
    return vault


def count_files(directory: Path) -> int:
    """Count non-hidden files in a directory."""
    if not directory.exists():
        return 0
    return sum(1 for f in directory.iterdir() if f.is_file() and not f.name.startswith("."))


def log_action(vault: Path, action_type: str, target: str, result: str, details: dict | None = None):
    """Append an action to today's log file."""
    logs_dir = vault / "Logs"
    logs_dir.mkdir(exist_ok=True)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action_type,
        "actor": "claude_code",
        "target": target,
        "result": result,
        "details": details or {},
    }

    log_file = logs_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except (json.JSONDecodeError, ValueError):
            entries = []

    entries.append(log_entry)
    log_file.write_text(json.dumps(entries, indent=2))


def update_dashboard(vault: Path):
    """Update Dashboard.md with current vault status."""
    now = datetime.now(timezone.utc)

    inbox_count = count_files(vault / "Inbox")
    needs_action_count = count_files(vault / "Needs_Action")
    pending_count = count_files(vault / "Pending_Approval")
    done_count = count_files(vault / "Done")

    # Read existing dashboard to preserve recent activity
    dashboard_path = vault / "Dashboard.md"
    existing_activity = []
    if dashboard_path.exists():
        content = dashboard_path.read_text()
        # Extract recent activity lines
        in_activity = False
        for line in content.split("\n"):
            if line.startswith("## Recent Activity"):
                in_activity = True
                continue
            if in_activity and line.startswith("| 2"):
                existing_activity.append(line)
            elif in_activity and line.startswith("##"):
                break

    # Keep only last 10 activity entries
    existing_activity = existing_activity[-10:]
    activity_rows = "\n".join(existing_activity) if existing_activity else "| _No recent activity_ | - | - |"

    dashboard_content = f"""---
last_updated: {now.isoformat()}
status: active
version: 0.1
---

# AI Employee Dashboard

## System Status
- **AI Employee**: Active
- **File Watcher**: Running
- **Last Check**: {now.strftime('%Y-%m-%d %H:%M UTC')}

## Pending Actions
| Folder | Count |
|--------|-------|
| Inbox | {inbox_count} |
| Needs Action | {needs_action_count} |
| Pending Approval | {pending_count} |
| Done | {done_count} |

## Recent Activity
| Timestamp | Action | Status |
|-----------|--------|--------|
{activity_rows}

## Weekly Stats
- **Tasks Completed**: {done_count}
- **Tasks Pending**: {needs_action_count + pending_count}
- **Files in Inbox**: {inbox_count}

---
*Auto-updated by AI Employee v0.1 at {now.strftime('%Y-%m-%d %H:%M UTC')}*
"""
    dashboard_path.write_text(dashboard_content)
    print(f"Dashboard updated: {inbox_count} inbox, {needs_action_count} needs_action, {done_count} done")


def list_pending(vault: Path):
    """List all items in Needs_Action."""
    needs_action = vault / "Needs_Action"
    items = sorted(needs_action.glob("*.md"))

    if not items:
        print("No pending items in Needs_Action.")
        return

    print(f"\n{'='*60}")
    print(f"  PENDING ITEMS ({len(items)})")
    print(f"{'='*60}\n")

    for item in items:
        content = item.read_text()
        # Extract frontmatter fields
        lines = content.split("\n")
        print(f"  - {item.name}")
        for line in lines:
            if line.startswith("original_name:") or line.startswith("priority:") or line.startswith("status:"):
                print(f"    {line.strip()}")
        print()


def main():
    vault = get_vault_path()

    if not vault.exists():
        print(f"ERROR: Vault not found at {vault}")
        sys.exit(1)

    action = sys.argv[2] if len(sys.argv) > 2 else "status"

    if action == "status":
        list_pending(vault)
        update_dashboard(vault)
    elif action == "update-dashboard":
        update_dashboard(vault)
    elif action == "list":
        list_pending(vault)
    else:
        print(f"Unknown action: {action}")
        print("Usage: python process_inbox.py [vault_path] [status|update-dashboard|list]")
        sys.exit(1)


if __name__ == "__main__":
    main()
