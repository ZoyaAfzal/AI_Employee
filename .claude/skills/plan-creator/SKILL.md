---
name: plan-creator
description: |
  Creates Plan.md files with reasoning loops for multi-step tasks.
  Analyzes a task, breaks it into actionable steps with checkboxes, saves to /Plans/,
  and tracks progress. Use when a task requires more than 2 steps or cross-domain reasoning.
---

# Plan Creator - AI Employee Skill

Transform complex tasks into structured Plan.md files stored in `AI_Employee_Vault/Plans/`.

## When to Use

Create a Plan.md when:
- A task in `/Needs_Action/` requires 3+ steps to complete
- A task involves multiple external systems (email + payment + social)
- An action needs human approval mid-way through
- A task should be tracked for the CEO Briefing

## Workflow: Create a Plan

### Step 1: Analyze the Task

Read the source file from `/Needs_Action/` thoroughly:
- What is the end goal?
- What systems/tools are needed?
- Are there approval gates?
- What are the dependencies (step B requires step A)?

### Step 2: Check Company Handbook

```bash
cat AI_Employee_Vault/Company_Handbook.md
```

Identify:
- Any approval thresholds that apply
- Tone/communication guidelines
- Action boundaries (what AI can auto-approve vs. what needs human sign-off)

### Step 3: Write the Plan File

Save to `AI_Employee_Vault/Plans/PLAN_<TASK_NAME>_<DATE>.md`

**Plan file format:**

```markdown
---
plan_id: PLAN_<TASK_NAME>_<YYYY-MM-DD>
created: <ISO_TIMESTAMP>
source_task: <SOURCE_FILE_IN_NEEDS_ACTION>
status: in_progress
priority: high|medium|low
estimated_steps: <N>
completed_steps: 0
---

# Plan: <TASK_TITLE>

## Context
<1-2 sentence summary of what needs to be done and why>

## Goal
<Clear, measurable outcome - what does "done" look like?>

## Steps

- [ ] **Step 1:** <Action> — Tool: <vault-manager|email-sender|linkedin-poster|browsing-with-playwright>
- [ ] **Step 2:** <Action> — Tool: <tool>
- [ ] **Step 3 (APPROVAL REQUIRED):** <Sensitive action> — Wait for: /Approved/<APPROVAL_FILE>
- [ ] **Step 4:** <Action> — Tool: <tool>
- [ ] **Step 5:** Log completion and update Dashboard.md

## Dependencies
- Step 3 requires approval before Step 4 can run
- Step 2 requires output from Step 1

## Approval Gates
| Step | Approval File | Threshold |
|------|--------------|-----------|
| Step 3 | APPROVAL_<NAME>_<DATE>.md | <Reason per handbook> |

## Notes
<Any edge cases, fallback behavior, or warnings>
```

### Step 4: Execute the Plan Step-by-Step

Work through each step in order:

```
FOR each unchecked step [ ] in the plan:
  1. Read the step description
  2. Invoke the appropriate skill (vault-manager, email-sender, etc.)
  3. If APPROVAL REQUIRED: create approval file, PAUSE, wait for /Approved/
  4. When approved: continue
  5. Mark step as complete: change [ ] to [x]
  6. Update plan frontmatter: completed_steps += 1
  7. Save the updated Plan.md
WHEN all steps are [x]:
  Update plan status: in_progress → completed
  Move source task to /Done/
  Update Dashboard.md
```

### Step 5: Update Dashboard After Each Step

After every step completion, update `AI_Employee_Vault/Dashboard.md`:
- Increment completed actions counter
- Add entry to Recent Activity
- Update plan progress (e.g., "Plan X: 3/5 steps complete")

## Plan Naming Convention

```
PLAN_<TASK_TYPE>_<SUBJECT>_<YYYY-MM-DD>.md

Examples:
PLAN_EMAIL_invoice_client_a_2026-02-28.md
PLAN_LINKEDIN_weekly_post_2026-02-28.md
PLAN_PAYMENT_subscription_renewal_2026-02-28.md
```

## Step Status Markers

| Symbol | Meaning |
|--------|---------|
| `[ ]` | Pending |
| `[x]` | Completed |
| `[~]` | In progress / waiting |
| `[!]` | Blocked (needs approval or dependency) |
| `[-]` | Skipped (not applicable) |

## Reasoning Loop Pattern

For complex tasks, use this reasoning loop before writing the plan:

```
THINK:
1. What is the trigger? (email / file drop / scheduled / manual)
2. What is the desired outcome?
3. What information is missing? (do I need to read more files?)
4. What tools are available? (skills in .claude/skills/)
5. What could go wrong? (network failure, missing approval, wrong data)
6. What is the minimum number of steps to reach the goal?

THEN: Write the plan with ONLY the necessary steps (no over-engineering)
```

## Example: Invoice Processing Plan

```markdown
---
plan_id: PLAN_INVOICE_client_b_2026-02-28
created: 2026-02-28T09:00:00Z
source_task: EMAIL_invoice_request_client_b.md
status: in_progress
priority: high
estimated_steps: 5
completed_steps: 0
---

# Plan: Process Invoice Request from Client B

## Context
Client B emailed requesting Invoice #1042 for $750 consulting work completed Jan 2026.

## Goal
Send signed invoice to client_b@example.com and log payment as pending.

## Steps

- [ ] **Step 1:** Read client details from AI_Employee_Vault/Contacts/client_b.md — Tool: vault-manager
- [ ] **Step 2:** Generate invoice markdown file in /Plans/ — Tool: vault-manager
- [ ] **Step 3 (APPROVAL REQUIRED):** Send invoice via email — Wait for: /Approved/EMAIL_invoice_client_b_2026-02-28.md
- [ ] **Step 4:** Log pending payment in /Accounting/Pending_Payments.md — Tool: vault-manager
- [ ] **Step 5:** Update Dashboard.md and move task to /Done/ — Tool: vault-manager

## Approval Gates
| Step | Approval File | Threshold |
|------|--------------|-----------|
| Step 3 | EMAIL_invoice_client_b_2026-02-28.md | Email to new/external contact |
```

## Rules

- ALWAYS create a plan before executing multi-step tasks
- NEVER skip approval gates defined in Company_Handbook.md
- ALWAYS update plan checkboxes as steps complete
- ALWAYS log the completed plan in `/Logs/`
- If a step fails: mark it `[!]`, add failure note, create error entry in log
- Plans are auditable records — never delete them, only archive to `/Done/`
