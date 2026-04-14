---
type: email
source: gmail
message_id: 19c5932e75bcfbba
thread_id: 19c5932e75bcfbba
from: Google Cloud <CloudPlatform-noreply@google.com>
reply_to: Google Cloud <CloudPlatform-noreply@google.com>
cc: 
subject: [Product Update] Automatic enablement of new OpenTelemetry ingestion API
received: 2026-02-13T14:50:33-08:00
priority: high
email_type: meeting
labels: ["UNREAD", "CATEGORY_UPDATES", "INBOX"]
status: pending
---

## Email: [Product Update] Automatic enablement of new OpenTelemetry ingestion API

**From:** Google Cloud <CloudPlatform-noreply@google.com>
**Received:** 2026-02-13T14:50:33-08:00
**Priority:** HIGH
**Type:** meeting

---

### Preview

We&#39;re enabling a new OTLP ingestion API starting Mar 23, 2026. MY CONSOLE Hello Zoya, You may have previously received a notification regarding this update. If so, please disregard this message. We

---

### Full Body

Hello Zoya,

We’re writing to let you know that Cloud Observability has launched a new  
OpenTelemetry (OTel) ingestion API[1] that supports native OpenTelemetry  
Protocol (OTLP) logs, trace spans, and metrics. Starting March 4, 2026,  
this API will be added as a dependency for the current Cloud Logging, Cloud  
Trace, and Cloud Monitoring ingestion APIs. This change ensures a seamless  
transition as collection tools migrate to this new unified endpoint.

What you need to know

Key changes:

    - The existing Cloud Observability ingestion APIs  
(logging.googleapis.com, cloudtrace.googleapis.com, and  
monitoring.googleapis.com) are automatically activated when you create a  
Google Cloud project using the Google Cloud console or gcloud CLI. The  
behavior remains unchanged for projects created via API, which do not have  
these ingestion APIs enabled by default. Starting March 4, 2026, the new  
OTel ingestion endpoint telemetry.googleapis.com will automatically  
activate when any of these specified APIs are enabled.
    - In addition, we will automatically enable this new endpoint for all  
existing projects that already have current ingestion APIs active.

What you need to do

No action is required from you for this API enablement change, and there  
will be no disruption to your existing services. You may disable the API at  
any time by following these instructions[2].

Refer to the attachment for a list of the projects that will automatically  
enable the new endpoint

We’re here to help

If you have any questions or require assistance, please contact Google  
Cloud Support[3].

Thanks for choosing Google Cloud Observability.

– The Google Cloud Team

[1]  
https://docs.cloud.google.com/stackdriver/docs/reference/telemetry/overview
[2] https://docs.cloud.google.com/service-usage/docs/enable-disable
[3] https://support.google.com/

© 2026 Google LLC 1600 Amphitheatre Parkway, Mountain View, CA 94043

You’ve 

---

## Suggested Actions

- [ ] Check calendar availability
- [ ] Draft meeting confirmation reply
- [ ] Create calendar event (requires approval)

---

_Source: Gmail Watcher | Message ID: 19c5932e75bcfbba_
