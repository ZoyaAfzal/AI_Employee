---
type: approval_request
action: odoo_post_invoice
invoice_id: 28
customer: TechStart Ltd (Test)
amount: $2875.00
created: 2026-05-09T00:00:00Z
status: pending
---

## Invoice Details

- **Invoice ID:** 28
- **Customer:** TechStart Ltd (Test) — accounts@techstart.io
- **Invoice Date:** 2026-05-09

### Line Items

| Description | Qty | Unit Price | Subtotal |
|-------------|-----|-----------|---------|
| Web Development — May 2026 | 20 | $100.00 | $2,000.00 |
| Monthly Maintenance Fee | 1 | $500.00 | $500.00 |

- **Subtotal:** $2,500.00
- **Tax (15%):** $375.00
- **Total:** $2,875.00
- **State:** Draft (not yet posted to accounting)

## To Approve

Move this file to the `/Approved` folder to post the invoice to Odoo accounting.

> **Warning:** Posting is irreversible. The invoice will be assigned a sequential number and affect your books.

## To Reject

Move this file to the `/Rejected` folder to discard this request. The draft invoice (ID=28) will remain in Odoo as a draft.
