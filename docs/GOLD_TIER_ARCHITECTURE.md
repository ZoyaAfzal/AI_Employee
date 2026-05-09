# Gold Tier Architecture — AI Employee

## Overview

Gold Tier builds on Silver Tier (multi-watcher, LinkedIn, Gmail MCP, approval workflow) by adding:

1. **Odoo Community** — self-hosted accounting via Docker Compose
2. **Facebook/Instagram Integration** — Graph API posting + monitoring
3. **Weekly CEO Briefing** — cross-domain data aggregation
4. **Ralph Wiggum Loop** — autonomous multi-step task completion
5. **Error recovery** — graceful degradation across all components
6. **Comprehensive audit logging** — JSON logs per day

---

## Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                    GOLD TIER AI EMPLOYEE                        │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                      EXTERNAL SOURCES                            │
├──────────┬───────────┬───────────┬──────────┬────────────────────┤
│  Gmail   │ LinkedIn  │ Facebook  │  Odoo    │  File System       │
│  (IMAP)  │(Playwright│(Graph API)│(JSON-RPC)│  (/Inbox)          │
└────┬─────┴─────┬─────┴─────┬─────┴────┬─────┴────────┬───────────┘
     ▼           ▼           ▼          ▼               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    PERCEPTION LAYER (Watchers)                   │
│  GmailWatcher  LinkedInWatcher  FacebookWatcher  FileSystemWatcher│
│  (gmail_watcher.py) (linkedin_watcher.py) (facebook_watcher.py)  │
└────────────────────────────────┬─────────────────────────────────┘
                                 │ Creates .md files
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    OBSIDIAN VAULT (Local)                        │
│  /Needs_Action  /Plans  /Done  /Logs  /Briefings                 │
│  Dashboard.md  Company_Handbook.md  Business_Goals.md            │
│  /Pending_Approval  /Approved  /Rejected                         │
└────────────────────────────────┬─────────────────────────────────┘
                                 │
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│               REASONING LAYER (Claude Code)                      │
│   Read → Think → Plan → Write → Request Approval                 │
│   Skills: vault-manager, email-sender, facebook-poster,          │
│           odoo-integration, ceo-briefing, ralph-wiggum           │
└──────────┬───────────────────────────────────────────────────────┘
           │
    ┌──────┴──────────────────────────┐
    ▼                                 ▼
┌──────────────────┐    ┌─────────────────────────────────────────┐
│ HUMAN-IN-THE-LOOP│    │           ACTION LAYER (MCP Servers)    │
│ /Pending_Approval│    │  Gmail MCP  Facebook MCP  Odoo MCP      │
│ Move → /Approved │───▶│  (gmail_mcp) (facebook_mcp) (odoo_mcp)  │
│ Move → /Rejected │    │  Vault MCP  Playwright MCP              │
└──────────────────┘    └──────────────────────────────────────────┘
                                       │
                        ┌──────────────┴───────────────┐
                        ▼                              ▼
               ┌────────────────┐          ┌──────────────────────┐
               │ Odoo Community │          │  Facebook/Instagram  │
               │  (Docker)      │          │  Graph API           │
               │  :8069         │          │  Posts, Comments     │
               └────────────────┘          └──────────────────────┘
```

---

## New Components (Gold Tier)

### 1. Odoo Docker Compose (`odoo/`)

```
odoo/
├── docker-compose.yml    # Odoo 17 + PostgreSQL 15
├── odoo.conf             # Odoo configuration
├── .env.example          # Copy to .env and configure
└── addons/               # Custom addons (empty by default)
```

**Start Odoo:**
```bash
cd odoo
cp .env.example .env
# Edit .env with secure passwords
docker compose up -d
# Access: http://localhost:8069
```

### 2. Odoo MCP Server (`mcp_servers/odoo_mcp/server.py`)

Tools: `odoo_list_invoices`, `odoo_create_invoice`, `odoo_post_invoice`,
`odoo_get_accounting_summary`, `odoo_list_customers`, `odoo_create_customer`,
`odoo_list_products`, `odoo_list_expenses`, `odoo_search_records`

**Configure in Claude Code settings:**
```json
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": ["mcp_servers/odoo_mcp/server.py"],
      "env": {
        "ODOO_URL": "http://localhost:8069",
        "ODOO_DB": "odoo",
        "ODOO_USERNAME": "admin",
        "ODOO_PASSWORD": "admin"
      }
    }
  }
}
```

### 3. Facebook MCP Server (`mcp_servers/facebook_mcp/server.py`)

Tools: `fb_post_to_page`, `fb_get_page_posts`, `fb_get_page_insights`,
`fb_post_to_instagram`, `fb_get_instagram_posts`, `fb_get_post_comments`,
`fb_reply_to_comment`, `fb_generate_summary`

**Configure in Claude Code settings:**
```json
{
  "mcpServers": {
    "facebook": {
      "command": "python",
      "args": ["mcp_servers/facebook_mcp/server.py"],
      "env": {
        "FB_PAGE_ID": "your_page_id",
        "FB_PAGE_ACCESS_TOKEN": "your_long_lived_page_token"
      }
    }
  }
}
```

### 4. Facebook Watcher (`watchers/facebook_watcher.py`)

Monitors:
- New comments on posts (keyword-triggered: price, buy, contact, etc.)
- New messages in Page inbox
- Creates action files in `/Needs_Action/`

### 5. CEO Briefing Generator (`watchers/ceo_briefing.py`)

Runs every Sunday night, generates Monday Morning CEO Briefing:
- Pulls accounting data from Odoo via JSON-RPC
- Counts vault task stats
- Aggregates social media summaries
- Writes to `/Briefings/YYYY-MM-DD_Monday_CEO_Briefing.md`

### 6. Ralph Wiggum Stop Hook (`.claude/hooks/stop.sh`)

Persistent loop for multi-step tasks:
- Intercepts Claude's exit
- Re-injects prompt if task not complete
- Max 10 iterations (configurable)
- State tracked in `/tmp/ralph_state.json`

---

## New Agent Skills (Gold Tier)

| Skill | File | Purpose |
|-------|------|---------|
| `facebook-poster` | `.claude/skills/facebook-poster/SKILL.md` | Post to FB/Instagram |
| `odoo-integration` | `.claude/skills/odoo-integration/SKILL.md` | Manage Odoo accounting |
| `ceo-briefing` | `.claude/skills/ceo-briefing/SKILL.md` | Generate CEO briefing |
| `ralph-wiggum` | `.claude/skills/ralph-wiggum/SKILL.md` | Persistence loop |

---

## Setup Checklist

### Phase 1: Odoo (Required)
- [ ] Install Docker Desktop
- [ ] `cd odoo && cp .env.example .env` — edit passwords
- [ ] `docker compose up -d`
- [ ] Open http://localhost:8069 and create database
- [ ] Install Invoicing module
- [ ] Configure company details
- [ ] Set `ODOO_PASSWORD` in .env to match your admin password
- [ ] Test: `python mcp_servers/odoo_mcp/server.py`
- [ ] Add `odoo` MCP server to Claude Code settings

### Phase 2: Facebook (Required)
- [ ] Create Facebook App at developers.facebook.com
- [ ] Add Pages API + Instagram Graph API permissions
- [ ] Get long-lived Page Access Token
- [ ] Set `FB_PAGE_ID` and `FB_PAGE_ACCESS_TOKEN` in .env
- [ ] Optional: Set `FB_INSTAGRAM_ID` for Instagram posting
- [ ] Test: `python mcp_servers/facebook_mcp/server.py`
- [ ] Add `facebook` MCP server to Claude Code settings
- [ ] Start Facebook watcher via orchestrator

### Phase 3: CEO Briefing (Optional but recommended)
- [ ] Verify Odoo connection works
- [ ] Test: `cd watchers && python ceo_briefing.py`
- [ ] Check output in `AI_Employee_Vault/Briefings/`
- [ ] Add cron job for Sunday night runs

### Phase 4: Ralph Wiggum (Optional)
- [ ] Verify `.claude/hooks/stop.sh` is executable: `chmod +x .claude/hooks/stop.sh`
- [ ] Check `.claude/settings.json` has Stop hook configured
- [ ] Test with simple task: `claude "List files in /tmp and output <TASK_COMPLETE>"`

---

## Environment Variables (.env)

```bash
# Silver Tier (existing)
VAULT_PATH=/path/to/AI_Employee_Vault
CLAUDE_PATH=claude
ENABLE_GMAIL=true
ENABLE_LINKEDIN=true
ENABLE_FILESYSTEM=true
LOG_ONLY=false

# Gold Tier (new)
ENABLE_FACEBOOK=true

# Odoo
ODOO_URL=http://localhost:8069
ODOO_DB=odoo
ODOO_USERNAME=admin
ODOO_PASSWORD=your_admin_password

# Facebook
FB_PAGE_ID=your_numeric_page_id
FB_PAGE_ACCESS_TOKEN=your_long_lived_page_token
FB_INSTAGRAM_ID=your_instagram_business_id  # optional
FB_CHECK_INTERVAL=300  # seconds between checks
```

---

## Lessons Learned

1. **Facebook Graph API** requires a long-lived Page Access Token (not user token). Page tokens for pages you manage are permanent and don't expire.

2. **Odoo JSON-RPC** requires session authentication first (`/web/session/authenticate`), then you can call `/web/dataset/call_kw` for model operations. The API is stable across Odoo 14-17.

3. **Docker Compose** for Odoo needs a health check on PostgreSQL before starting Odoo (`depends_on: db: condition: service_healthy`), otherwise Odoo crashes on first boot.

4. **Ralph Wiggum** Stop hook exit code 2 re-injects the prompt. Exit 0 allows exit. The hook must be fast (< 2 seconds) or Claude Code times it out.

5. **CEO Briefing** aggregates multiple data sources — always use `try/except` per source so one failure doesn't break the entire briefing.
