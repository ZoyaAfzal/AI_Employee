---
name: vault-manager
description: |
  Manages the AI Employee Obsidian vault. Processes files in /Needs_Action,
  updates Dashboard.md, moves completed items to /Done, and maintains audit logs.
  Use when tasks involve reading, processing, or organizing vault contents.
---

# Vault Manager - AI Employee Skill

Manage the AI Employee Obsidian vault at `AI_Employee_Vault/`.

## Vault Structure

```
AI_Employee_Vault/
├── Dashboard.md          # Real-time status summary (update after every action)
├── Company_Handbook.md   # Rules of engagement (read before acting)
├── Inbox/                # Raw incoming files (watcher drops files here)
├── Needs_Action/         # Files awaiting processing (metadata .md files)
├── Plans/                # Action plans created by Claude
├── Pending_Approval/     # Items needing human approval
├── Approved/             # Human-approved actions
├── Rejected/             # Human-rejected actions
├── Done/                 # Completed items (archive)
├── Logs/                 # JSON audit logs (daily files)
└── Briefings/            # Generated reports and briefings
```

## Core Operations

### 1. Process Needs_Action Items

Read all `.md` files in `/Needs_Action/`, understand the task, execute it, and move to `/Done/`.

```bash
# List pending items
ls AI_Employee_Vault/Needs_Action/

# After processing, move both the metadata and source file to Done
mv AI_Employee_Vault/Needs_Action/FILE_*.md AI_Employee_Vault/Done/
mv AI_Employee_Vault/Needs_Action/FILE_*.txt AI_Employee_Vault/Done/
```

### 2. Update Dashboard

After every action, update `Dashboard.md` with current status:
- Count files in each folder
- Log the action in Recent Activity
- Update stats

### 3. Create Audit Logs

Every action must be logged to `Logs/YYYY-MM-DD.json`:

```json
{
  "timestamp": "2026-02-25T10:00:00Z",
  "action_type": "file_processed",
  "actor": "claude_code",
  "target": "FILE_invoice.md",
  "result": "success",
  "details": {}
}
```

### 4. Check Company Handbook

Before any action, read `Company_Handbook.md` to verify the action is within allowed thresholds. If the action requires approval, create a file in `/Pending_Approval/` instead of acting directly.

## Workflow: Process Inbox Item

1. Read the `.md` file in `/Needs_Action/` to understand what needs doing
2. Read `Company_Handbook.md` to check approval thresholds
3. If auto-approved: process the item, log it, move to `/Done/`
4. If needs approval: create approval file in `/Pending_Approval/`, log it
5. Update `Dashboard.md` with the action taken

## Workflow: Update Dashboard

1. Count files: `ls Inbox/ Needs_Action/ Pending_Approval/ Done/`
2. Read current `Dashboard.md`
3. Update counts, recent activity, and timestamp
4. Write updated `Dashboard.md`

## Rules

- ALWAYS read `Company_Handbook.md` before taking sensitive actions
- NEVER delete original files - always move/copy
- ALWAYS log actions to `/Logs/`
- ALWAYS update `Dashboard.md` after changes
- If uncertain, create a file in `/Pending_Approval/` for human review
