# Gmail MCP Server — Setup Instructions

## 1. Install dependencies

```bash
cd mcp_servers/gmail_mcp
pip install -r requirements.txt
```

Or from the watchers folder (if using uv):
```bash
cd watchers
uv add mcp google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## 2. Authorise Gmail (one-time)

```bash
cd watchers
python gmail_auth.py
```

This opens a browser for Google OAuth consent. After authorising, a token is saved at:
`watchers/credentials/token.json`

## 3. Register with Claude Code

Add the following to your Claude Code MCP configuration.

**On Linux/WSL — edit `~/.claude.json`** (or run `claude mcp add`):

```json
{
  "mcpServers": {
    "gmail": {
      "command": "python",
      "args": [
        "/mnt/c/Users/Admin/OneDrive/Desktop/AI_Employee/mcp_servers/gmail_mcp/server.py"
      ],
      "env": {
        "VAULT_PATH": "/mnt/c/Users/Admin/OneDrive/Desktop/AI_Employee/AI_Employee_Vault",
        "GMAIL_TOKEN_PATH": "/mnt/c/Users/Admin/OneDrive/Desktop/AI_Employee/watchers/credentials/token.json"
      }
    }
  }
}
```

> Replace the paths with your actual absolute paths.

## 4. Verify

In Claude Code, type:
```
/mcp
```

You should see `gmail` listed with tools:
- `send_email`
- `draft_email`
- `search_emails`
- `get_email`
- `list_unread`
- `reply_email`

## 5. Test

Ask Claude:
> "Use the gmail MCP to list my 5 most recent unread important emails"

## Available Tools

| Tool | Description | Approval Required? |
|------|-------------|-------------------|
| `list_unread` | List unread important emails | No |
| `search_emails` | Search by Gmail query | No |
| `get_email` | Fetch full email by ID | No |
| `draft_email` | Save to Gmail Drafts | No |
| `send_email` | Send an email | Yes — approval file in /Approved/ |
| `reply_email` | Reply to a thread | Yes (external contacts) |

## Security Notes

- `send_email` requires an `approval_file` parameter pointing to an existing file in
  `AI_Employee_Vault/Approved/`. If the file doesn't exist, the send is blocked.
- Tokens are stored locally, never in the vault or in git.
- `.env` and `credentials/` are in `.gitignore`.
