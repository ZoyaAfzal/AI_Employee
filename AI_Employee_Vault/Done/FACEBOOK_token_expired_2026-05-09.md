---
type: action_required
priority: HIGH
category: auth_error
platform: facebook
created: 2026-05-09T00:00:00Z
status: needs_action
---

# ACTION REQUIRED: Facebook Access Token Expired

The Facebook Page access token expired on **2026-05-08 at 15:00 PDT**.
All Facebook and Instagram posting is paused until the token is refreshed.

## How to Refresh the Token

### Option A — Graph API Explorer (Easiest)
1. Go to https://developers.facebook.com/tools/explorer/
2. Select your App and your Page
3. Click **Generate Access Token**
4. Select permissions: `pages_manage_posts`, `pages_read_engagement`
5. Copy the new Page Access Token

### Option B — Exchange for Long-Lived Token
```bash
# Step 1: Get long-lived user token (60 days)
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN"

# Step 2: Get permanent page token
curl "https://graph.facebook.com/v19.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN"
```

## After Refreshing

Update `FB_PAGE_ACCESS_TOKEN` in:
- `/home/zoyaafzal/.claude/settings.json` → `mcpServers.facebook.env.FB_PAGE_ACCESS_TOKEN`

Then retry the pending Facebook post saved at:
`AI_Employee_Vault/Drafts/FACEBOOK_draft_business_announcement_2026-05-09.md`
