---
name: odoo-integration
description: |
  Manages Odoo Community accounting, invoicing, and CRM via JSON-RPC MCP server.
  Handles creating/posting invoices, managing customers, products, and generating
  accounting summaries. Always requires human approval before posting invoices.
  Use when tasks involve invoices, customers, expenses, or accounting data.
---

# Odoo Integration — AI Employee Skill (Gold Tier)

Interact with Odoo 17 Community (self-hosted via Docker) through the Odoo MCP server.

## Prerequisites

- Odoo running: `cd odoo && docker compose up -d`
- Odoo MCP server configured in Claude Code settings (`odoo` server)
- Environment vars: `ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`

## Starting Odoo

```bash
# Start Odoo + PostgreSQL via Docker Compose
cd /path/to/AI_Employee/odoo
docker compose up -d

# Check status
docker compose ps
docker compose logs odoo --tail=20

# Access Odoo Web UI
# http://localhost:8069
# Default: admin / admin (change immediately)

# Stop
docker compose down
```

## First-Time Odoo Setup

1. Open http://localhost:8069
2. Create database with your company details
3. Install modules: **Invoicing** (required), **Accounting** (recommended), **Contacts**
4. Set up your company: Settings → General Settings → Company
5. Configure fiscal year and chart of accounts

## Workflow: Create and Send an Invoice

### Step 1: Find or Create Customer
```
Tool: odoo_list_customers
Parameters: {search: "customer name", limit: 5}
```

If customer not found:
```
Tool: odoo_create_customer
Parameters: {name: "Customer Name", email: "email@example.com", phone: "+1234567890"}
```

### Step 2: Check Available Products
```
Tool: odoo_list_products
Parameters: {search: "service name", limit: 10}
```

### Step 3: Create Invoice (Draft)
```
Tool: odoo_create_invoice
Parameters:
  customer_name: "Customer Name"
  lines:
    - description: "Consulting Services - January 2026"
      quantity: 10
      price_unit: 150.00
      product_name: "Consulting"
  notes: "Payment due within 30 days"
```

This creates a **DRAFT** invoice — it does NOT affect accounting until posted.

### Step 4: Create Approval Request

Per Company Handbook, posting invoices requires human approval:

```markdown
# Create: AI_Employee_Vault/Pending_Approval/ODOO_invoice_<customer>_<date>.md
---
type: approval_request
action: odoo_post_invoice
invoice_id: <ID from Step 3>
customer: <customer name>
amount: $<total>
created: <ISO_TIMESTAMP>
status: pending
---

## Invoice Details
- Customer: <name>
- Amount: $<total>
- Lines: <service description>

## To Approve
Move this file to /Approved folder.
```

### Step 5: Post Invoice (after approval)
```
Tool: odoo_post_invoice
Parameters:
  invoice_id: <ID>
  approval_file: "/path/to/AI_Employee_Vault/Approved/ODOO_invoice_*.md"
```

## Workflow: Monthly Accounting Summary

```
Tool: odoo_get_accounting_summary
Parameters: {month: "2026-04"}
```

Returns:
- Total invoiced, paid, outstanding
- Total expenses
- Net profit estimate
- Top 10 invoices

## Workflow: List Expenses / Bills

```
Tool: odoo_list_expenses
Parameters: {state: "posted", limit: 20}
```

## Workflow: CEO Briefing Accounting Data

The `ceo-briefing` skill calls the Odoo MCP to populate the revenue section.
You can also run manually:

```bash
# Generate CEO briefing with Odoo data
cd watchers && python ceo_briefing.py
```

## Useful Odoo MCP Tools

| Tool | Purpose |
|------|---------|
| `odoo_list_invoices` | View all invoices by state |
| `odoo_get_invoice` | Get full invoice details + lines |
| `odoo_create_invoice` | Create draft invoice |
| `odoo_post_invoice` | Confirm/post draft (irreversible) |
| `odoo_list_customers` | Search customers |
| `odoo_create_customer` | Add new customer |
| `odoo_list_products` | Search products/services |
| `odoo_get_accounting_summary` | Monthly P&L summary |
| `odoo_list_expenses` | View vendor bills |
| `odoo_search_records` | Generic Odoo model search |

## Rules

- NEVER post (confirm) an invoice without a file in `/Approved/`
- NEVER delete records — set to cancelled state instead
- ALWAYS create draft first, then review, then post after approval
- Log all Odoo actions to `/Logs/`
- Update Dashboard.md after significant accounting events
- For payments over $100 → always require fresh human approval

## Docker Compose Maintenance

```bash
# View logs
docker compose logs -f odoo

# Restart Odoo only (keep DB)
docker compose restart odoo

# Backup database
docker exec odoo_db pg_dump -U odoo odoo > backup_$(date +%Y%m%d).sql

# Restore database
docker exec -i odoo_db psql -U odoo odoo < backup_20260419.sql

# Update to new Odoo version
docker compose pull && docker compose up -d

# Full reset (WARNING: deletes all data)
docker compose down -v
```

## Error Handling

- Odoo not reachable → check `docker compose ps`, run `docker compose up -d`
- Authentication error → verify ODOO_USERNAME and ODOO_PASSWORD
- Invoice post failed → check draft state, required fields
- Database locked → restart: `docker compose restart odoo`
