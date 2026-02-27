---
type: approval_request
action: invoice_processing
amount: 500.00
client: Test Client
invoice_number: "001"
reason: Invoice #001 - payment of $500 from Test Client
created: 2026-02-25T00:00:00Z
status: pending
flagged_keywords: ["payment"]
handbook_rule: "Financial Rules - Flag any transaction over $100 for human approval"
---

## Invoice Review Required

**Invoice #:** 001
**Client:** Test Client
**Amount:** $500.00
**Date:** 2026-02-25

## Why Approval Is Required
- Amount exceeds $100 auto-approve threshold (Company Handbook - Financial Rules)
- Contains flagged keyword: "payment" (Company Handbook - Communication Rules)

## Original File Location
- Inbox: `/Inbox/test_invoice.txt`
- Needs_Action: `/Needs_Action/FILE_test_invoice.txt`

## To Approve
Move this file to `/Approved/` folder.

## To Reject
Move this file to `/Rejected/` folder.
