#!/usr/bin/env bash
# Ralph Wiggum Stop Hook — Gold Tier
#
# Called by Claude Code's Stop hook before Claude exits.
# Checks if there is an active Ralph loop task that needs more work.
#
# Exit codes:
#   0 — allow exit (task complete or no active task)
#   2 — block exit and re-inject prompt (task still in progress)

RALPH_STATE="/tmp/ralph_state.json"
LOG_FILE="${RALPH_LOG:-/tmp/ralph_wiggum.log}"
MAX_ITERATIONS=10

log() {
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] [RalphWiggum] $1" >> "$LOG_FILE"
}

# No active Ralph task → allow exit
if [ ! -f "$RALPH_STATE" ]; then
    exit 0
fi

# Read state
TASK_ID=$(python3 -c "import json,sys; d=json.load(open('$RALPH_STATE')); print(d.get('task_id',''))" 2>/dev/null)
PROMPT=$(python3 -c "import json,sys; d=json.load(open('$RALPH_STATE')); print(d.get('prompt',''))" 2>/dev/null)
COMPLETION_FILE=$(python3 -c "import json,sys; d=json.load(open('$RALPH_STATE')); print(d.get('completion_file',''))" 2>/dev/null)
CURRENT_ITER=$(python3 -c "import json,sys; d=json.load(open('$RALPH_STATE')); print(d.get('current_iteration',0))" 2>/dev/null)
MAX_ITER=$(python3 -c "import json,sys; d=json.load(open('$RALPH_STATE')); print(d.get('max_iterations',$MAX_ITERATIONS))" 2>/dev/null)
STATUS=$(python3 -c "import json,sys; d=json.load(open('$RALPH_STATE')); print(d.get('status','active'))" 2>/dev/null)

# Already marked complete
if [ "$STATUS" = "complete" ]; then
    log "Task $TASK_ID marked complete — allowing exit"
    rm -f "$RALPH_STATE"
    exit 0
fi

# Max iterations reached → allow exit to prevent infinite loop
if [ "$CURRENT_ITER" -ge "$MAX_ITER" ]; then
    log "Task $TASK_ID reached max iterations ($MAX_ITER) — allowing exit"
    python3 -c "
import json
d = json.load(open('$RALPH_STATE'))
d['status'] = 'max_iterations_reached'
json.dump(d, open('$RALPH_STATE','w'), indent=2)
" 2>/dev/null
    exit 0
fi

# Check file-based completion signal
if [ -n "$COMPLETION_FILE" ] && [ -f "$COMPLETION_FILE" ]; then
    log "Task $TASK_ID completed (completion file found: $COMPLETION_FILE)"
    rm -f "$RALPH_STATE" "$COMPLETION_FILE"
    exit 0
fi

# Check stdout for TASK_COMPLETE token
# (Claude Code passes last response via stdin in some hook configurations)
if [ -t 0 ]; then
    : # no stdin
else
    STDIN_CONTENT=$(cat 2>/dev/null)
    if echo "$STDIN_CONTENT" | grep -q "TASK_COMPLETE"; then
        log "Task $TASK_ID completed (TASK_COMPLETE token found in output)"
        rm -f "$RALPH_STATE"
        exit 0
    fi
fi

# Task still in progress — increment counter and re-inject prompt
NEW_ITER=$((CURRENT_ITER + 1))
log "Task $TASK_ID: iteration $NEW_ITER/$MAX_ITER — re-injecting prompt"

python3 -c "
import json
d = json.load(open('$RALPH_STATE'))
d['current_iteration'] = $NEW_ITER
json.dump(d, open('$RALPH_STATE','w'), indent=2)
" 2>/dev/null

# Output the re-inject prompt to stdout — Claude Code reads this when exit code is 2
echo "$PROMPT"

# Exit code 2 = re-inject prompt and continue
exit 2
