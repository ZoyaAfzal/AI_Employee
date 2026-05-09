---
type: approval_request
action: odoo_post_invoice
invoice_id: 27
customer: Acme Corp (Test)
amount: $1725.00
created: 2026-05-09T00:00:00Z
status: pending
---

## Invoice Details

- **Invoice ID:** 27
- **Customer:** Acme Corp (Test) — billing@acmecorp.com
- **Invoice Date:** 2026-05-09
- **Line Item:** Consulting Services — May 2026
  - Quantity: 10 × $150.00 = $1,500.00
  - Tax: $225.00
- **Total:** $1,725.00
- **State:** Draft (not yet posted to accounting)

## To Approve

Move this file to the `/Approved` folder to post the invoice to Odoo accounting.

> **Warning:** Posting is irreversible. The invoice will be assigned a sequential number and affect your books.

## To Reject

Move this file to the `/Rejected` folder to discard this approval request. The draft invoice (ID=27) will remain in Odoo as a draft.
