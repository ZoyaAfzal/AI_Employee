---
name: ralph-wiggum
description: |
  The Ralph Wiggum persistence loop — keeps Claude working autonomously until
  a multi-step task is fully complete. Uses a Stop hook that re-injects the
  prompt if the task hasn't moved to /Done yet.
  Use when starting a long multi-step task that must complete without human re-prompting.
---

# Ralph Wiggum Loop — AI Employee Skill (Gold Tier)

The Ralph Wiggum pattern keeps Claude iterating on a task until completion using
a Stop hook that re-injects the prompt when Claude tries to exit prematurely.

## How It Works

```
1. You create a task state file in /tmp/ralph_state.json
2. Claude processes the task
3. Claude tries to exit
4. Stop hook (.claude/hooks/stop.sh) runs:
   - Checks if task completion file exists in /Done
   - NO → re-injects the original prompt (Claude continues)
   - YES → allows exit (task complete)
5. Repeat until done or max iterations reached
```

## Usage

### Option A: Promise-based (simple)
Ask Claude to output `<TASK_COMPLETE>` when done.
The Stop hook watches for this string and exits cleanly.

```bash
# Start a Ralph loop task
claude "Process all files in AI_Employee_Vault/Needs_Action and move each to /Done when processed. Output <TASK_COMPLETE> when all files are done."
```

### Option B: File-movement based (reliable)
Create a state file that the Stop hook monitors:

```bash
# Create state file
cat > /tmp/ralph_state.json << 'EOF'
{
  "task_id": "process_inbox_2026-04-19",
  "prompt": "Process all files in AI_Employee_Vault/Needs_Action. For each file: read it, take appropriate action, move to /Done. When ALL files are in /Done, create the file /tmp/ralph_state.json with status=complete.",
  "completion_file": "/tmp/ralph_done_process_inbox_2026-04-19",
  "max_iterations": 10,
  "current_iteration": 0
}
EOF

# Run Claude with the Ralph loop
claude "$(cat /tmp/ralph_state.json | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d[\"prompt\"])')"
```

### Option C: Via the Stop hook (automatic)

When `.claude/hooks/stop.sh` is configured in `.claude/settings.json`, every time
Claude tries to stop it automatically checks for pending work and re-prompts if needed.

## Stop Hook Setup

The stop hook is at `.claude/hooks/stop.sh` and is configured in `.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash /path/to/.claude/hooks/stop.sh"
          }
        ]
      }
    ]
  }
}
```

The hook:
- Checks `/tmp/ralph_state.json` for active task
- If task not complete (no completion file) → exits with code 2 (re-prompts Claude)
- If task complete or no active task → exits with code 0 (allows exit)
- Increments iteration counter, exits cleanly if max_iterations reached

## Task Completion Signals

### Signal 1: Output the completion token
Claude outputs `<TASK_COMPLETE>` anywhere in its response.

### Signal 2: Create the completion file
```python
# Claude creates this file to signal completion:
Path("/tmp/ralph_done_<task_id>").touch()
```

### Signal 3: Move task to /Done
```bash
# Claude moves the original task file from /Needs_Action to /Done
mv AI_Employee_Vault/Needs_Action/TASK_FILE.md AI_Employee_Vault/Done/
```

## Example: Process All Vault Files

```
Task: Process all Needs_Action files in a single autonomous run

Prompt for Ralph loop:
"Check AI_Employee_Vault/Needs_Action/ for unprocessed files.
For each .md file found:
1. Read the file
2. Determine the appropriate action (email reply, archive, flag)
3. Take the action or create an approval request
4. Move the file to /Done
5. Update Dashboard.md
Repeat until Needs_Action is empty.
When completely done, output <TASK_COMPLETE>."
```

## Safeguards

- **Max iterations**: Default 10, configurable in state file
- **Timeout**: Each iteration has a 5-minute timeout
- **Error state**: If Claude errors 3 times in a row, loop exits and notifies human
- **Human override**: Delete `/tmp/ralph_state.json` to stop the loop
- **Audit trail**: Each iteration logged to `/Vault/Logs/<DATE>.json`

## When to Use Ralph Wiggum

✅ Use for:
- Processing a large batch of files in /Needs_Action
- Multi-step invoice workflow (create → review → post)
- Weekly audit with multiple data sources
- Any task requiring >3 sequential Claude interactions

❌ Don't use for:
- Single-step tasks (just run Claude once)
- Tasks requiring human input at each step
- Real-time interactive tasks
- Payment/financial operations (too sensitive for full automation)
