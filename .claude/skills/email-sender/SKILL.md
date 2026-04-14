---
name: email-sender
description: |
  Sends, drafts, and manages emails via Gmail using the Gmail API or SMTP.
  Handles composing replies, sending invoices, and forwarding messages.
  Use when a task requires sending or drafting an email. Always checks approval
  workflow before sending to new contacts or bulk recipients.
---

# Email Sender - AI Employee Skill

Send and draft emails via Gmail for the AI Employee.

## Prerequisites

Credentials stored in `.env`:
```
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REFRESH_TOKEN=your_refresh_token
GMAIL_SENDER_ADDRESS=your@gmail.com
```

Or use the Gmail watcher script credentials at `watchers/credentials/gmail_credentials.json`.

## Approval Gate

**ALWAYS check before sending:**

| Recipient Type | Auto-Approve | Requires Approval |
|---------------|--------------|-------------------|
| Known contact (in vault) | ✅ Replies only | New emails |
| New/external contact | ❌ Never | Always |
| Bulk send (2+ recipients) | ❌ Never | Always |
| Email with attachment > 1MB | ❌ Never | Always |

If approval is required → follow the Approval Workflow skill first.

## Workflow: Send an Email

### Step 1: Draft the Email Content

Compose the email following Company_Handbook.md tone guidelines:

```
Subject line: Clear, specific, professional
Body structure:
  - Greeting (Dear [Name] / Hi [Name])
  - Context (1 sentence - why you're writing)
  - Main content (2-4 sentences or bullet list)
  - Call to action (what you need from them)
  - Sign-off (Best regards / Kind regards)
  - Signature block
```

### Step 2: Check Approval Requirements

```bash
# Check if recipient is a known contact
grep -r "<RECIPIENT_EMAIL>" AI_Employee_Vault/ 2>/dev/null | head -5
```

- If known contact replying to existing thread → may auto-approve (check handbook)
- If new contact or new thread → create approval file first (see below)

### Step 3a: Create Approval File (if required)

Save to `AI_Employee_Vault/Pending_Approval/EMAIL_<SUBJECT>_<DATE>.md`:

```markdown
---
type: approval_request
action: send_email
to: <RECIPIENT_EMAIL>
subject: <EMAIL_SUBJECT>
created: <ISO_TIMESTAMP>
expires: <ISO_TIMESTAMP_PLUS_24H>
status: pending
---

## Email Preview

**To:** <RECIPIENT>
**Subject:** <SUBJECT>

---

<FULL_EMAIL_BODY>

---

## To Approve
Move this file to /Approved folder.

## To Reject
Move this file to /Rejected folder.
```

Wait for the file to appear in `/Approved/` before proceeding.

### Step 3b: Send via Python Script

Once approved (or auto-approved), send using Python + Gmail API:

```python
# email_send.py - run with: python3 watchers/email_send.py
import os
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def send_email(to, subject, body, credentials_path='watchers/credentials/gmail_credentials.json'):
    creds = Credentials.from_authorized_user_file(credentials_path)
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    result = service.users().messages().send(
        userId='me',
        body={'raw': raw}
    ).execute()
    return result['id']
```

Run the script:
```bash
python3 -c "
import sys
sys.path.insert(0, 'watchers')
# Load .env
from pathlib import Path
for line in Path('.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        import os; os.environ[k.strip()] = v.strip()
"
```

### Step 4: Verify Send

After sending, verify success:

```bash
# Check sent mail (optional, via Gmail API search)
python3 -c "
# Search sent mail for confirmation
print('Email sent successfully - check Gmail Sent folder')
"
```

### Step 5: Log the Action

```python
# Log format for /Logs/YYYY-MM-DD.json
log_entry = {
    "timestamp": "<ISO_TIMESTAMP>",
    "action_type": "email_send",
    "actor": "claude_code",
    "target": "<RECIPIENT_EMAIL>",
    "parameters": {
        "subject": "<SUBJECT>",
        "to": "<RECIPIENT>"
    },
    "approval_status": "approved|auto_approved",
    "approved_by": "human|auto",
    "result": "success|failure"
}
```

Update `Dashboard.md` to reflect the email action.

## Workflow: Draft Email (No Send)

For drafting without sending (save to Gmail Drafts):

```python
def create_draft(to, subject, body, credentials_path):
    creds = Credentials.from_authorized_user_file(credentials_path)
    service = build('gmail', 'v1', credentials=creds)

    message = MIMEText(body)
    message['to'] = to
    message['subject'] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = service.users().drafts().create(
        userId='me',
        body={'message': {'raw': raw}}
    ).execute()
    return draft['id']
```

Save draft details to `AI_Employee_Vault/Pending_Approval/DRAFT_<SUBJECT>_<DATE>.md` for human review.

## Common Email Templates

### Invoice Email
```
Subject: Invoice #<NUMBER> - <SERVICE> - <YOUR_COMPANY>

Dear <CLIENT_NAME>,

Please find attached Invoice #<NUMBER> for <SERVICE DESCRIPTION> completed on <DATE>.

Invoice Details:
- Amount: $<AMOUNT>
- Due Date: <DUE_DATE>
- Payment Method: <PAYMENT_INSTRUCTIONS>

Please let me know if you have any questions.

Best regards,
<YOUR_NAME>
<YOUR_COMPANY>
```

### Follow-up Email
```
Subject: Following up - <ORIGINAL_SUBJECT>

Hi <NAME>,

I wanted to follow up on my previous email from <DATE> regarding <TOPIC>.

<2-3 sentences of context>

Please let me know if you need any additional information.

Best regards,
<YOUR_NAME>
```

### Meeting Confirmation
```
Subject: Confirmed: <MEETING_TOPIC> - <DATE/TIME>

Hi <NAME>,

This confirms our meeting:
- Date: <DATE>
- Time: <TIME> (<TIMEZONE>)
- Location/Link: <LOCATION>
- Agenda: <AGENDA_ITEMS>

Looking forward to speaking with you.

Best regards,
<YOUR_NAME>
```

## Gmail API Setup (one-time)

If credentials don't exist yet:

1. Go to Google Cloud Console → Enable Gmail API
2. Create OAuth 2.0 credentials → Download as `credentials.json`
3. Run the auth flow:
```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
python3 watchers/gmail_auth.py  # generates token.json
```

## Rules

- NEVER send emails without checking approval requirements
- NEVER expose email addresses in logs (use first letter + domain: j***@gmail.com)
- ALWAYS log every email send action
- ALWAYS update Dashboard.md after sending
- Rate limit: max 10 emails per hour (per Company Handbook)
- If Gmail API is unavailable: queue to `/Pending_Approval/` with note "API unavailable"
