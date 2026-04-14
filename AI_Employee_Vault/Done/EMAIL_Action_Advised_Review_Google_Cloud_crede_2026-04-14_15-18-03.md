---
type: email
source: gmail
message_id: 19c41de0591a40d9
thread_id: 19c41de0591a40d9
from: Google Cloud <CloudPlatform-noreply@google.com>
reply_to: Google Cloud <CloudPlatform-noreply@google.com>
cc: 
subject: [Action Advised] Review Google Cloud credential security best practices
received: 2026-02-09T02:06:35-08:00
priority: high
email_type: finance
labels: ["UNREAD", "CATEGORY_UPDATES", "INBOX"]
status: pending
---

## Email: [Action Advised] Review Google Cloud credential security best practices

**From:** Google Cloud <CloudPlatform-noreply@google.com>
**Received:** 2026-02-09T02:06:35-08:00
**Priority:** HIGH
**Type:** finance

---

### Preview

Secure service account and API keys to prevent unauthorized access. MY CONSOLE Hello Zoya, We&#39;re writing to provide you with security best practices regarding the management of service account keys

---

### Full Body

Secure service account and API keys to prevent unauthorized access.




MY CONSOLE




Hello Zoya,

We're writing to provide you with security best practices regarding the  
management of service account keys and API keys within your Google Cloud  
environment.

Recent security trends indicate that long-lived credentials without proper  
security best practices remain a top security risk for unauthorized access.  
To ensure your environment remains secure, and to modernize your  
authentication strategy, we strongly advise implementing the unified  
security framework outlined below.

What you need to do

Action advised:

Secure the credential lifecycle: Apply standard security hygiene by  
following these best practices:


Zero-Code Storage: Never commit keys to source code or version control. Use  
Secret Manager to inject credentials at runtime.
Disable Dormant Keys: Audit your active keys and decommission any that show  
no activity over the last 30 days.
Enforce API Restrictions: Never leave an API key unrestricted. Limit keys  
to specific APIs (eg, Maps Java Script only) and apply environmental  
restrictions (IP addresses, HTTP referrers, or bundle IDs).
Apply Least Privilege: Never give full permissions to a service account.  
Use the IAM recommender to prune unused permissions for service accounts,  
ensuring only the absolute minimum access required for their function.
Mandatory Rotation: Implement the iam.serviceAccountKeyExpiryHours policy  
to enforce a maximum lifespan for all user-managed service account keys. If  
service account keys are not needed, implement  
iam.managed.disableServiceAccountKeyCreation to disable the creation of new  
service account keys.

Improve operational safeguards: Ensure a rapid response to security  
incidents by completing the following:


Set Essential Contacts: Verify that your Essential Contacts are up to date  
to ensure critical security notifications reach the ri

---

## Suggested Actions

- [ ] Review invoice/payment details
- [ ] Check against Accounting records
- [ ] Approve or flag for human review
- [ ] Reply with acknowledgement (requires approval)

---

_Source: Gmail Watcher | Message ID: 19c41de0591a40d9_
