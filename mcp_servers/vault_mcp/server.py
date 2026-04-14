"""
Vault MCP Server — AI Employee

Exposes AI Employee Vault file operations as MCP tools so the orchestrator
can read, write, move, and log without going through the Claude CLI.

Tools:
  vault_list_folder     : list files in a vault sub-folder
  vault_read_file       : read a vault file (relative to vault root)
  vault_write_file      : create / overwrite a vault file
  vault_move_file       : move a file between vault folders
  vault_log_action      : append an entry to the daily JSON log
  vault_update_dashboard: replace a named section in Dashboard.md

Add to Claude Code MCP settings (or ~/.claude.json):
{
  "mcpServers": {
    "vault": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_servers/vault_mcp/server.py"],
      "env": {
        "VAULT_PATH": "/absolute/path/to/AI_Employee_Vault"
      }
    }
  }
}
"""

import os
import sys
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone

try:
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.types import Tool, TextContent, CallToolResult
except ImportError:
    print("ERROR: mcp package not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# ── config ─────────────────────────────────────────────────────────────────────
VAULT_PATH = Path(
    os.getenv("VAULT_PATH", Path(__file__).parent.parent.parent / "AI_Employee_Vault")
)
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [VaultMCP] %(levelname)s: %(message)s",
)
logger = logging.getLogger("VaultMCP")

# ── safety: only allow paths inside the vault ──────────────────────────────────

def _safe_path(relative: str) -> Path:
    """Resolve a relative vault path and reject any traversal attempts."""
    resolved = (VAULT_PATH / relative).resolve()
    if not str(resolved).startswith(str(VAULT_PATH.resolve())):
        raise ValueError(f"Path traversal rejected: {relative!r}")
    return resolved


# ── helpers ────────────────────────────────────────────────────────────────────

def _log_action(action: str, target: str, result: str, details: dict | None = None):
    logs_dir = VAULT_PATH / "Logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action_type": action,
        "actor": "vault_mcp",
        "target": target,
        "result": result,
        "details": details or {},
    }
    entries = []
    if log_file.exists():
        try:
            entries = json.loads(log_file.read_text())
        except Exception:
            entries = []
    entries.append(entry)
    log_file.write_text(json.dumps(entries, indent=2))


# ── MCP server ─────────────────────────────────────────────────────────────────

server = Server("vault-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="vault_list_folder",
            description=(
                "List files in a vault sub-folder (e.g. 'Needs_Action', 'Approved', "
                "'Pending_Approval', 'Done', 'Logs'). Returns filenames, one per line."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Sub-folder name relative to vault root (e.g. 'Needs_Action')",
                    },
                    "pattern": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g. 'EMAIL_*.md')",
                        "default": "*.md",
                    },
                },
                "required": ["folder"],
            },
        ),
        Tool(
            name="vault_read_file",
            description="Read the full text content of a vault file (relative path from vault root).",
            inputSchema={
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path relative to vault root, e.g. 'Needs_Action/EMAIL_foo.md'",
                    },
                },
                "required": ["relative_path"],
            },
        ),
        Tool(
            name="vault_write_file",
            description=(
                "Create or overwrite a vault file. "
                "Use for approval requests, briefings, Needs_Action entries, etc."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "relative_path": {
                        "type": "string",
                        "description": "Path relative to vault root, e.g. 'Pending_Approval/EMAIL_foo_2026-04-14.md'",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write",
                    },
                },
                "required": ["relative_path", "content"],
            },
        ),
        Tool(
            name="vault_move_file",
            description=(
                "Move a file from one vault folder to another "
                "(e.g. Pending_Approval → Approved, Approved → Done)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "from_path": {
                        "type": "string",
                        "description": "Source path relative to vault root",
                    },
                    "to_folder": {
                        "type": "string",
                        "description": "Destination folder name (e.g. 'Done', 'Rejected')",
                    },
                },
                "required": ["from_path", "to_folder"],
            },
        ),
        Tool(
            name="vault_log_action",
            description="Append an action entry to today's JSON log in AI_Employee_Vault/Logs/.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action_type": {"type": "string", "description": "e.g. 'email_send', 'approval_created'"},
                    "target": {"type": "string", "description": "What was acted on (file name, email, etc.)"},
                    "result": {"type": "string", "description": "e.g. 'success', 'pending', 'rejected'"},
                    "details": {
                        "type": "object",
                        "description": "Optional extra key/value pairs",
                        "default": {},
                    },
                },
                "required": ["action_type", "target", "result"],
            },
        ),
        Tool(
            name="vault_update_dashboard",
            description=(
                "Replace or append a named section in Dashboard.md. "
                "If section_heading exists, its content is replaced; otherwise appended."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "section_heading": {
                        "type": "string",
                        "description": "Exact markdown heading text, e.g. '## Pending Approvals'",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "Replacement content for the section (exclude the heading line)",
                    },
                },
                "required": ["section_heading", "new_content"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    try:
        if name == "vault_list_folder":
            return _vault_list_folder(**arguments)
        elif name == "vault_read_file":
            return _vault_read_file(**arguments)
        elif name == "vault_write_file":
            return _vault_write_file(**arguments)
        elif name == "vault_move_file":
            return _vault_move_file(**arguments)
        elif name == "vault_log_action":
            return _vault_log_action(**arguments)
        elif name == "vault_update_dashboard":
            return _vault_update_dashboard(**arguments)
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True,
            )
    except Exception as e:
        logger.error(f"Tool {name} error: {e}")
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )


# ── tool implementations ───────────────────────────────────────────────────────

def _vault_list_folder(folder: str, pattern: str = "*.md") -> CallToolResult:
    target = _safe_path(folder)
    if not target.exists():
        return CallToolResult(
            content=[TextContent(type="text", text=f"Folder does not exist: {folder}")]
        )
    files = sorted(target.glob(pattern))
    if not files:
        return CallToolResult(
            content=[TextContent(type="text", text=f"No files matching '{pattern}' in {folder}")]
        )
    names = "\n".join(f.name for f in files)
    return CallToolResult(
        content=[TextContent(type="text", text=f"Files in {folder}:\n{names}")]
    )


def _vault_read_file(relative_path: str) -> CallToolResult:
    path = _safe_path(relative_path)
    if not path.exists():
        return CallToolResult(
            content=[TextContent(type="text", text=f"File not found: {relative_path}")],
            isError=True,
        )
    content = path.read_text(encoding="utf-8")
    return CallToolResult(
        content=[TextContent(type="text", text=content)]
    )


def _vault_write_file(relative_path: str, content: str) -> CallToolResult:
    if DRY_RUN:
        return CallToolResult(
            content=[TextContent(type="text", text=f"[DRY RUN] Would write: {relative_path}")]
        )
    path = _safe_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _log_action("vault_write", relative_path, "success")
    logger.info(f"Written: {relative_path}")
    return CallToolResult(
        content=[TextContent(type="text", text=f"Written: {relative_path}")]
    )


def _vault_move_file(from_path: str, to_folder: str) -> CallToolResult:
    if DRY_RUN:
        return CallToolResult(
            content=[TextContent(type="text", text=f"[DRY RUN] Would move {from_path} -> {to_folder}/")]
        )
    src = _safe_path(from_path)
    dst_dir = _safe_path(to_folder)
    if not src.exists():
        return CallToolResult(
            content=[TextContent(type="text", text=f"Source not found: {from_path}")],
            isError=True,
        )
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    src.rename(dst)
    _log_action("vault_move", src.name, "success",
                {"from": from_path, "to": str(dst.relative_to(VAULT_PATH))})
    logger.info(f"Moved: {from_path} -> {to_folder}/{src.name}")
    return CallToolResult(
        content=[TextContent(type="text", text=f"Moved: {src.name} -> {to_folder}/")]
    )


def _vault_log_action(action_type: str, target: str, result: str,
                      details: dict | None = None) -> CallToolResult:
    _log_action(action_type, target, result, details)
    return CallToolResult(
        content=[TextContent(type="text", text=f"Logged: {action_type} -> {target} [{result}]")]
    )


def _vault_update_dashboard(section_heading: str, new_content: str) -> CallToolResult:
    if DRY_RUN:
        return CallToolResult(
            content=[TextContent(type="text", text=f"[DRY RUN] Would update Dashboard section: {section_heading}")]
        )
    dashboard = VAULT_PATH / "Dashboard.md"
    if not dashboard.exists():
        dashboard.write_text(f"# AI Employee Dashboard\n\n{section_heading}\n{new_content}\n")
        return CallToolResult(
            content=[TextContent(type="text", text="Dashboard created with new section.")]
        )

    text = dashboard.read_text(encoding="utf-8")
    # Find the section and replace until the next same-level or higher heading
    heading_level = len(re.match(r"^(#+)", section_heading).group(1)) if re.match(r"^(#+)", section_heading) else 2
    pattern = re.compile(
        rf"({re.escape(section_heading)}\n)(.*?)(?=\n{'#' * heading_level}[^#]|\Z)",
        re.DOTALL,
    )
    replacement = f"{section_heading}\n{new_content}\n"
    if pattern.search(text):
        text = pattern.sub(replacement, text, count=1)
    else:
        text = text.rstrip() + f"\n\n{section_heading}\n{new_content}\n"

    # Update last_updated in frontmatter if present
    text = re.sub(
        r"(last_updated:\s*).*",
        f"last_updated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        text,
        count=1,
    )
    dashboard.write_text(text, encoding="utf-8")
    return CallToolResult(
        content=[TextContent(type="text", text=f"Dashboard section updated: {section_heading}")]
    )


# ── entry point ────────────────────────────────────────────────────────────────

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
