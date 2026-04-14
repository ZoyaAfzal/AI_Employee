---
name: approval-workflow
description: |
  Manages the human-in-the-loop approval workflow for sensitive actions.
  Creates approval request files, monitors /Approved and /Rejected folders,
  and triggers or cancels downstream actions based on human decisions.
  Use when any action exceeds auto-approval thresholds in Company_Handbook.md.
---

# Approval Workflow - AI Employee Skill

Human-in-the-loop (HITL) system for sensitive actions. The AI writes an approval request
and waits for the human to move it to `/Approved/` or `/Rejected/` before acting.

## When to Use

Trigger this workflow when an action:
- Involves sending money or payments of **any amount**
- Sends email to a **new/unknown contact**
- Posts on **social media** (unless pre-scheduled and pre-approved)
- **Deletes or moves files** outside the vault
- Exceeds thresholds defined in `Company_Handbook.md`

## Approval Thresholds (Default)

| Action | Auto-Approve | Requires Approval |
|--------|-------------|-------------------|
| Email reply (known contact) | ✅ | — |
| Email to new contact | ❌ | Always |
| Payment < $50 (recurring) | ✅ | — |
| Payment > $50 or new payee | ❌ | Always |
| LinkedIn scheduled post | ✅ | — |
| LinkedIn new/unplanned post | ❌ | Always |
| File create/read in vault | ✅ | — |
| File delete or external move | ❌ | Always |

> Always re-read `Company_Handbook.md` — thresholds may have been updated.

## Workflow: Request Approval

### Step 1: Create the Approval Request File

Save to `AI_Employee_Vault/Pending_Approval/<TYPE>_<SUBJECT>_<DATE>.md`

**Naming convention:**
```
EMAIL_<SUBJECT>_<YYYY-MM-DD>.md        → email sends
PAYMENT_<RECIPIENT>_<YYYY-MM-DD>.md    → payments
LINKEDIN_<TOPIC>_<YYYY-MM-DD>.md       → social posts
FILE_<ACTION>_<TARGET>_<YYYY-MM-DD>.md → file operations
```

**Approval file format:**
```markdown
---
type: approval_request
action: <ACTION_TYPE>
subject: <BRIEF_DESCRIPTION>
created: <ISO_TIMESTAMP>
expires: <ISO_TIMESTAMP + 24H>
status: pending
risk_level: low|medium|high
---

## What the AI Wants to Do

<Clear 1-2 sentence description of the exact action>

## Why

<Reason this action was triggered - context from source task>

## Details

<Action-specific details - email preview, payment breakdown, post text, etc.>

## Risk Assessment

- **Risk level:** <low|medium|high>
- **Reversible:** <yes|no>
- **Impact if wrong:** <brief description>

## To Approve

Move this file to:
```
AI_Employee_Vault/Approved/
```

## To Reject

Move this file to:
```
AI_Employee_Vault/Rejected/
```
Add a comment below if you want to provide a reason:
<!-- REJECTION REASON: -->
```

### Step 2: Update Dashboard

After creating the approval file, update `Dashboard.md`:
```markdown
## Pending Approvals
- [ ] <ACTION_TYPE>: <SUBJECT> — Created: <DATE> — Expires: <EXPIRY>
```

Also log to `/Logs/YYYY-MM-DD.json`:
```json
{
  "timestamp": "<ISO>",
  "action_type": "approval_requested",
  "actor": "claude_code",
  "target": "<APPROVAL_FILE>",
  "result": "pending",
  "details": {"action": "<ACTION>", "subject": "<SUBJECT>"}
}
```

### Step 3: Monitor for Decision

Poll the `/Approved/` and `/Rejected/` folders:

```bash
# Check if approval was granted
ls AI_Employee_Vault/Approved/ | grep "<APPROVAL_FILENAME>"

# Check if rejected
ls AI_Employee_Vault/Rejected/ | grep "<APPROVAL_FILENAME>"
```

**Decision logic:**
- File found in `/Approved/` → proceed with the action
- File found in `/Rejected/` → cancel action, log rejection, notify via Dashboard
- File still in `/Pending_Approval/` after expiry → treat as rejected, log as expired

### Step 4: Act on the Decision

**If APPROVED:**
```
1. Read the approved file to confirm no changes were made to the request
2. Execute the approved action (call appropriate skill)
3. Move the approval file to /Done/
4. Log action with approval_status: "approved", approved_by: "human"
5. Update Dashboard.md
```

**If REJECTED:**
```
1. Read the rejection file for any rejection reason (in comments)
2. Cancel the planned action
3. Move the rejection file to /Done/
4. Log action with approval_status: "rejected", result: "cancelled"
5. Update Dashboard.md with rejection note
6. If task is still pending: create new Needs_Action entry with note "Rejected: <REASON>"
```

**If EXPIRED (no decision within 24h):**
```
1. Move approval file to /Rejected/ with expiry note
2. Log as expired
3. Update Dashboard.md
```

## Workflow: Check Pending Approvals

Use this sub-workflow to process any decisions the human has made:

```bash
# List all files in Approved folder
ls AI_Employee_Vault/Approved/

# List all files in Rejected folder
ls AI_Employee_Vault/Rejected/
```

For each file found:
1. Identify the original action from the filename
2. Find the corresponding plan or task
3. Execute Step 4 above based on folder (Approved vs Rejected)

## Expiry Management

Approval requests expire after **24 hours** by default (configurable in Company_Handbook.md).

Check for expired approvals:
```bash
# Find approval files older than 24h
find AI_Employee_Vault/Pending_Approval/ -name "*.md" -mmin +1440
```

Move expired files:
```bash
mv AI_Employee_Vault/Pending_Approval/<EXPIRED_FILE> AI_Employee_Vault/Rejected/
```

Add to the file:
```markdown
<!-- SYSTEM NOTE: Expired - no human decision within 24 hours -->
```

## Dashboard Integration

The Dashboard.md should always reflect current approval queue:

```markdown
## Pending Approvals (requires your action)
| Type | Subject | Created | Expires | Risk |
|------|---------|---------|---------|------|
| EMAIL | Invoice Client B | 2026-02-28 09:00 | 2026-03-01 09:00 | Low |
| PAYMENT | Subscription renewal | 2026-02-28 10:30 | 2026-03-01 10:30 | Medium |
```

## Notification Pattern

When a new approval is created, the AI should make it visible by:
1. Updating `Dashboard.md` (primary notification)
2. Placing the approval file prominently (top of Pending_Approval folder — use date prefix)
3. Optionally: writing a summary to `AI_Employee_Vault/Inbox/ATTENTION_REQUIRED_<DATE>.md`

## Rules

- NEVER act on a sensitive action without creating an approval file first
- NEVER auto-approve payment to a new payee (no exceptions)
- ALWAYS log approval requests, approvals, and rejections
- ALWAYS respect expiry — expired = rejected
- ALWAYS update Dashboard.md when approval status changes
- If the same action is rejected 2+ times: escalate with a note in Dashboard.md
