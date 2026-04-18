---
name: facebook-poster
description: |
  Posts business updates to Facebook Page and Instagram Business account.
  Uses Facebook Graph API via the Facebook MCP server.
  Generates weekly engagement summaries and logs all activity.
  Use when you need to post to Facebook/Instagram or generate social media reports.
---

# Facebook & Instagram Poster — AI Employee Skill (Gold Tier)

Post business content to Facebook Page and Instagram Business account via the Facebook MCP server.

## Prerequisites

- Facebook MCP server configured in Claude Code settings (`facebook` server)
- Environment vars set: `FB_PAGE_ID`, `FB_PAGE_ACCESS_TOKEN`, optionally `FB_INSTAGRAM_ID`
- For Instagram posting: Instagram Business Account linked to your Facebook Page

## Setting Up Facebook App & Access Token

### Step 1: Create a Facebook App
1. Go to https://developers.facebook.com/apps and create a new app
2. App type: **Business**
3. Add products: **Pages API**, **Instagram Graph API**
4. Required permissions: `pages_manage_posts`, `pages_read_engagement`, `pages_messaging`, `instagram_basic`, `instagram_content_publish`

### Step 2: Get a Long-Lived Page Access Token
```bash
# 1. Get short-lived token from Graph API Explorer
# 2. Exchange for long-lived user token (60 days):
curl "https://graph.facebook.com/v19.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN"

# 3. Get Page Access Token (permanent for pages):
curl "https://graph.facebook.com/v19.0/me/accounts?access_token=LONG_LIVED_USER_TOKEN"
# Use the page token from the response — it never expires for managed pages
```

### Step 3: Configure in .env
```
FB_PAGE_ID=your_numeric_page_id
FB_PAGE_ACCESS_TOKEN=your_page_access_token
FB_INSTAGRAM_ID=your_instagram_business_account_id  # optional
```

## Workflow: Post to Facebook

### Step 1: Craft Post Content

Best practices for Facebook business posts:
- Hook in first line (question, stat, bold claim)
- 2-4 short paragraphs
- Clear call-to-action
- 2-5 relevant hashtags
- Max 63,206 characters (aim for under 500 for engagement)

### Step 2: Check Approval Requirements

Per `Company_Handbook.md` — scheduled posts auto-approved, unplanned posts require approval:

```markdown
# Create approval file if unscheduled post:
AI_Employee_Vault/Pending_Approval/FACEBOOK_<TOPIC>_<DATE>.md
```

Approval file format:
```markdown
---
type: approval_request
action: facebook_post
topic: <TOPIC>
platform: facebook
created: <ISO_TIMESTAMP>
status: pending
---

## Post Preview
<FULL_POST_CONTENT>

## To Approve
Move this file to /Approved folder.
```

### Step 3: Post to Facebook Page

Use the `fb_post_to_page` MCP tool:
```
Tool: fb_post_to_page
Parameters:
  message: "Your post content here\n\nWith hashtags #Business #AI"
  link: "https://yoursite.com" (optional)
  published: true
```

### Step 4: Post to Instagram (if needed)

Instagram requires a publicly accessible image URL:
```
Tool: fb_post_to_instagram
Parameters:
  image_url: "https://example.com/image.jpg"
  caption: "Caption with hashtags #tag1 #tag2"
```

### Step 5: Log Activity

After successful post, update vault:
```bash
# Append to today's log
echo '{"timestamp":"ISO","action_type":"facebook_post","result":"success","details":{"preview":"..."}}' >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json

# Update Dashboard.md Recent Activity section
```

## Workflow: Generate Engagement Summary

Use `fb_generate_summary` to create a weekly report:
```
Tool: fb_generate_summary
Parameters:
  period_days: 7
  save_to_vault: true
```

The summary is saved to `AI_Employee_Vault/Briefings/<DATE>_Social_Media_Summary.md`.

## Workflow: Monitor Comments

When `FacebookWatcher` creates a `FACEBOOK_comment_*.md` in Needs_Action:

1. Read the file and assess priority
2. If `keyword_match: true` → draft reply, create approval request
3. Use `fb_get_post_comments` to get full thread context
4. Use `fb_reply_to_comment` with an approved file

## Post Templates

### Business Announcement
```
🚀 [Exciting update about your business]

[2-3 sentences expanding the update]

[Why this matters to your audience]

Want to know more? DM us or comment below!

#YourBusiness #[Industry] #AI
```

### Weekly Value Post
```
[Bold insight or useful tip]

Here's what we've learned about [TOPIC]:

→ [Point 1]
→ [Point 2]
→ [Point 3]

[Closing thought or question]

What's your take? Comment below 👇

#[Tag1] #[Tag2] #[Tag3]
```

### Client Win / Social Proof
```
🎉 [Client result or milestone — anonymized]

The approach: [Brief explanation]

If you're struggling with [problem], we can help.

[CTA — DM/visit link]

#ClientSuccess #[Industry]
```

## Rules

- NEVER post client-confidential information
- NEVER post pricing without approval
- ALWAYS check `Company_Handbook.md` for tone guidelines
- ALWAYS log posts and interactions to `/Logs/`
- ALWAYS update `Dashboard.md` after posting
- Limit: max 3 Facebook posts per day, max 1 Instagram post per day
- If API error → log error, create action file, do NOT retry automatically

## Error Handling

- Token expired → log HIGH priority alert in Dashboard.md, create action file
- Rate limit → wait and retry (max 3 attempts), then flag for human
- Post failed → save draft to `AI_Employee_Vault/Drafts/FACEBOOK_draft_<DATE>.md`
