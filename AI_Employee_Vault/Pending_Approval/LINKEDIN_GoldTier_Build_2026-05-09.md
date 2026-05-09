---
type: approval_request
action: linkedin_post
topic: Gold Tier AI Employee Build
created: 2026-05-09T06:45:00Z
status: pending
---

## Post Preview

I built a Gold Tier AI Employee — a fully autonomous business assistant running 24/7 on my local machine.

Here's what it actually does:

→ Reads & processes every Gmail email automatically
→ Creates invoices in Odoo accounting (with human approval gates)
→ Posts to LinkedIn and Facebook on schedule
→ Generates a weekly Monday CEO briefing — revenue, tasks, alerts
→ Manages 200+ tasks through an Obsidian vault with zero manual filing

No SaaS subscriptions. Runs entirely on my own hardware.

What I built:
- 4 custom MCP (Model Context Protocol) servers — Odoo, Gmail, Facebook, Vault
- Python watchers monitoring Gmail, LinkedIn, Facebook & filesystem in real time
- Odoo 17 Community self-hosted via Docker Compose for real accounting
- Human-in-the-loop approval workflow for sensitive actions (invoices, new contacts)
- The Ralph Wiggum persistence loop — Claude keeps working until the task is fully done, no re-prompting needed

Stack & tools used:
- Claude Code (Anthropic) as the AI brain
- MCP protocol for native tool integration
- Docker + PostgreSQL for self-hosted Odoo ERP
- Facebook Graph API, Gmail API, Odoo JSON-RPC
- Playwright for browser automation (LinkedIn posting)
- Python for all watchers and MCP server code
- Obsidian as the vault/task management layer

This isn't a demo. It's running live — processing real emails, drafting real invoices, posting real content.

Building AI that works in your business is about orchestration, not just the model. The model is Claude. The architecture is everything else.

Want to build something like this? DM me — happy to share the full breakdown.

#AIEmployee #ClaudeCode #MCP #BuildInPublic #AIAutomation #Odoo #Python #Automation

## To Approve
Move this file to /Approved folder.

## To Reject
Move this file to /Rejected folder.
