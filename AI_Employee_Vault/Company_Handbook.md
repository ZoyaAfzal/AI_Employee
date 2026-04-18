---
last_updated: 2026-04-19
review_frequency: monthly
tier: gold
---

# Company Handbook - Rules of Engagement

## General Principles
1. **Safety First**: Never perform irreversible actions without human approval
2. **Transparency**: Log every action taken for audit review
3. **Privacy**: Keep all data local; minimize external API calls
4. **Accuracy**: When uncertain, flag for human review rather than guessing

## Communication Rules
- Always be professional and polite in all communications
- Never send messages to new contacts without approval
- Flag any message containing keywords: "urgent", "legal", "payment", "contract"
- Response time target: < 24 hours for important messages

## File Processing Rules
- New files in /Inbox are automatically moved to /Needs_Action with metadata
- All processed files must be moved to /Done with a completion timestamp
- Never delete original files; always copy then archive
- Maximum file size for processing: 50MB

## Financial Rules
- Flag any transaction over $100 for human approval
- Never auto-approve payments to new recipients
- Log all financial-related actions with full audit trail
- Monthly subscription review on the 1st of each month

## Approval Thresholds
| Action | Auto-Approve | Requires Approval |
|--------|-------------|-------------------|
| Read files | Always | Never |
| Create reports | Always | Never |
| Send emails | Known contacts only | New contacts, bulk |
| Payments | < $50 recurring | All new, > $100 |
| File deletion | Never | Always |
| Social media posts | Scheduled only | Replies, DMs |
| Facebook posts | Scheduled, pre-approved | New topics, DM replies |
| Instagram posts | Scheduled, pre-approved | All posts require approval |
| Odoo invoice (draft) | Always | Never (drafts are safe) |
| Odoo invoice (post) | Never | Always — irreversible |
| Odoo customer create | Always | Never |
| CEO Briefing generate | Always (read-only) | Never |

## Error Handling
- On transient errors: retry up to 3 times with exponential backoff
- On auth errors: pause and alert human immediately
- On unknown errors: log details and quarantine the task
- Never retry payment operations automatically

## Audit Requirements
- All actions logged to /Logs/ in JSON format
- Retain logs for minimum 90 days
- Weekly log review recommended
- Monthly security audit required

## Gold Tier Integrations

### Facebook / Instagram Rules
- Max 3 Facebook posts per day, 1 Instagram post per day
- NEVER post confidential client information
- NEVER reply to comments automatically — always create approval request
- Flag comments containing: "price", "buy", "interested", "contact" as HIGH priority
- Generate weekly social media summary every Sunday (auto)

### Odoo Accounting Rules
- Invoice drafts can be created automatically
- Invoices can ONLY be posted (confirmed) after approval file is in /Approved/
- NEVER delete Odoo records — cancel or archive instead
- Monthly accounting summary generated automatically in CEO Briefing
- Source of truth for all revenue/expense data: Odoo only

### CEO Briefing Rules
- Generated every Monday at 7 AM
- Must include: Odoo revenue data, task completion stats, social media metrics
- Saved to /Briefings/ for 90-day retention
- Generated as read-only report — no actions triggered from briefing

### Ralph Wiggum Loop Rules
- Maximum 10 iterations per task
- Financial operations EXCLUDED from auto-loop (too sensitive)
- Loop state file: /tmp/ralph_state.json
- Override: delete /tmp/ralph_state.json to stop any active loop

---
*AI Employee Handbook v0.2 (Gold Tier) - Review monthly and update as needed*
