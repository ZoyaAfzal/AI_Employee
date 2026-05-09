---
type: approval_request
action: linkedin_post
topic: Gold Tier AI Employee Build — Odoo + Facebook
created: 2026-05-09T06:50:00Z
status: pending
---

## Post Preview

Gold Tier unlocked: I gave my AI Employee real accounting and social media superpowers.

This week I completed the Gold Tier of my AI Employee build. Here's what it added:

Odoo 17 Accounting (self-hosted)
→ Claude can now create draft invoices, look up customers, and pull a full monthly P&L summary
→ Runs locally via Docker Compose + PostgreSQL — no subscription, no cloud dependency
→ Every invoice post requires human approval before it touches the books

Facebook Graph API integration
→ Claude posts to my Facebook Business Page and Instagram automatically
→ Can pull page insights, read comments, and reply — all via a custom MCP server
→ Generates weekly engagement summaries without opening the app

Weekly CEO Briefing
→ Every Monday morning, Claude aggregates Odoo revenue data + Facebook engagement into one business health report
→ Catches blockers, flags alerts, and surfaces top tasks — before the first coffee

What I built under the hood:
- 2 custom MCP (Model Context Protocol) servers in Python — one for Odoo JSON-RPC, one for Facebook Graph API
- Odoo 17 Community running in Docker with a custom odoo.conf and PostgreSQL
- Human-in-the-loop approval workflow — invoices and social posts require a file moved to /Approved before execution
- 3 new Claude Code skills: odoo-integration, facebook-poster, ceo-briefing

The system now handles accounting + social media without me touching either platform.

Next up: connecting it all to close the sales loop end to end.

DM me if you're building something similar — happy to compare notes.

#AIEmployee #ClaudeCode #MCP #Odoo #FacebookAPI #BuildInPublic #AIAutomation #Python

## To Approve
Move this file to /Approved folder.

## To Reject
Move this file to /Rejected folder.
