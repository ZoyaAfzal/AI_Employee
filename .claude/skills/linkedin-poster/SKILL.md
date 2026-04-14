---
name: linkedin-poster
description: |
  Automatically posts business updates to LinkedIn to generate sales and visibility.
  Crafts professional posts, handles LinkedIn login via Playwright, and logs all activity.
  Use when you need to post business content, promotions, or updates on LinkedIn.
---

# LinkedIn Poster - AI Employee Skill

Post business content to LinkedIn automatically using Playwright browser automation.

## Prerequisites

- Playwright MCP server running on port 8808 (start with `bash scripts/start-server.sh`)
- LinkedIn credentials stored in `.env` as `LINKEDIN_EMAIL` and `LINKEDIN_PASSWORD`
- OR an active LinkedIn session saved at `watchers/sessions/linkedin_session/`

## Workflow: Post to LinkedIn

### Step 1: Prepare the Post Content

Before posting, craft the content based on the task context:

```
Business post best practices:
- Lead with value or a hook (question, stat, insight)
- 3-5 short paragraphs, each 1-3 lines
- End with a call-to-action (DM, comment, visit link)
- Add 3-5 relevant hashtags at the end
- Max 3,000 characters for full posts
```

### Step 2: Start Playwright and Navigate to LinkedIn

```bash
# Start Playwright MCP server if not running
bash scripts/start-server.sh

# Navigate to LinkedIn
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_navigate \
  -p '{"url": "https://www.linkedin.com"}'
```

### Step 3: Check Login State

```bash
# Take snapshot to check if already logged in
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_snapshot -p '{}'
```

- If you see the feed/home page → already logged in, skip Step 4
- If you see the login page → proceed with Step 4

### Step 4: Login (if needed)

```bash
# Navigate to login
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_navigate \
  -p '{"url": "https://www.linkedin.com/login"}'

# Get snapshot to find input refs
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_snapshot -p '{}'

# Fill email (use ref from snapshot)
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_type \
  -p '{"element": "Email field", "ref": "<email_ref>", "text": "<LINKEDIN_EMAIL>"}'

# Fill password
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_type \
  -p '{"element": "Password field", "ref": "<password_ref>", "text": "<LINKEDIN_PASSWORD>", "submit": true}'

# Wait for login to complete
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_wait_for \
  -p '{"text": "Home", "timeout": 10000}'
```

### Step 5: Create a New Post

```bash
# Click the "Start a post" button
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_navigate \
  -p '{"url": "https://www.linkedin.com/feed/"}'

python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_snapshot -p '{}'

# Click "Start a post" (find ref from snapshot)
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_click \
  -p '{"element": "Start a post", "ref": "<start_post_ref>"}'

# Wait for modal to open
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_wait_for \
  -p '{"text": "What do you want to talk about?", "timeout": 5000}'
```

### Step 6: Type Post Content

```bash
# Get snapshot to find the text area ref
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_snapshot -p '{}'

# Type your post content (replace with actual content)
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_type \
  -p '{"element": "Post text area", "ref": "<textarea_ref>", "text": "<POST_CONTENT>"}'
```

### Step 7: Submit the Post

```bash
# Get snapshot to find Post button
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_snapshot -p '{}'

# Click Post button
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_click \
  -p '{"element": "Post button", "ref": "<post_button_ref>"}'

# Wait for confirmation
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_wait_for \
  -p '{"text": "Post successful", "timeout": 10000}'

# Take screenshot for audit trail
python3 scripts/mcp-client.py call -u http://localhost:8808 -t browser_take_screenshot \
  -p '{"type": "png"}'
```

### Step 8: Log the Post

After a successful post, log it to the vault:

```bash
# Append to daily log
cat >> AI_Employee_Vault/Logs/$(date +%Y-%m-%d).json << 'EOF'
{
  "timestamp": "<ISO_TIMESTAMP>",
  "action_type": "linkedin_post",
  "actor": "claude_code",
  "target": "linkedin",
  "result": "success",
  "details": {
    "content_preview": "<FIRST_100_CHARS>",
    "hashtags": ["<TAG1>", "<TAG2>"]
  }
}
EOF
```

Update `Dashboard.md` with the posting activity.

## Approval Workflow

LinkedIn posts are **social media posts** and require approval per Company_Handbook.md.

Before posting:
1. Check `Company_Handbook.md` for social media posting policy
2. If scheduled posts are pre-approved → post directly
3. If new/unplanned post → create approval file first:

```
AI_Employee_Vault/Pending_Approval/LINKEDIN_<TOPIC>_<DATE>.md
```

**Approval file format:**
```markdown
---
type: approval_request
action: linkedin_post
topic: <TOPIC>
created: <ISO_TIMESTAMP>
status: pending
---

## Post Preview

<FULL_POST_CONTENT>

## To Approve
Move this file to /Approved folder.

## To Reject
Move this file to /Rejected folder.
```

Watch `/Approved/` - when this file appears there, proceed with posting.

## Post Templates

### Business Update Post
```
🚀 [Exciting update about your business]

[2-3 sentences expanding on the update]

[Why this matters to your audience]

Want to learn more? [CTA - DM / comment / link]

#YourIndustry #BusinessGrowth #[RelevantTag]
```

### Value/Tips Post
```
[Bold claim or surprising fact]

Here's what most people miss about [TOPIC]:

1. [Point one]
2. [Point two]
3. [Point three]

[Closing insight]

What's your experience with [TOPIC]? Drop a comment 👇

#[Tag1] #[Tag2] #[Tag3]
```

### Client Win Post
```
🎉 Excited to share a win from this week!

[Client/project result without revealing confidential info]

The key was [insight or approach].

If you're facing [common problem], I'd love to help.

#[Industry] #ClientSuccess #[Tag]
```

## Rules

- NEVER post client-confidential information
- NEVER post pricing without approval
- ALWAYS check `Company_Handbook.md` for tone guidelines
- ALWAYS log posts in `/Logs/`
- ALWAYS update `Dashboard.md` after posting
- Limit: max 2 posts per day (per Company Handbook)
- If login fails (2FA, CAPTCHA), create file in `/Pending_Approval/` for manual review
