"""
MCP Client — AI Employee

Thin synchronous wrapper around the async MCP SDK.
Lets the orchestrator (sync) call MCP server tools directly
without spawning a Claude CLI subprocess.

Usage:
    from mcp_client import call_vault_tool, call_gmail_tool, get_all_tools

    # Call a vault tool
    result = call_vault_tool("vault_list_folder", {"folder": "Needs_Action"})

    # Call a gmail tool
    result = call_gmail_tool("list_unread", {"max_results": 5})

    # Get all tool schemas (for Anthropic API tool_use)
    tools = get_all_tools()   # list of dicts with name/description/input_schema
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("MCPClient")

# ── paths ──────────────────────────────────────────────────────────────────────
WATCHERS_DIR = Path(__file__).parent
PROJECT_DIR = WATCHERS_DIR.parent

VAULT_PATH = Path(os.getenv("VAULT_PATH", str(PROJECT_DIR / "AI_Employee_Vault")))
TOKEN_PATH = Path(
    os.getenv(
        "GMAIL_TOKEN_PATH",
        str(WATCHERS_DIR / "credentials" / "token.json"),
    )
)

VAULT_MCP_SCRIPT = str(PROJECT_DIR / "mcp_servers" / "vault_mcp" / "server.py")
GMAIL_MCP_SCRIPT = str(PROJECT_DIR / "mcp_servers" / "gmail_mcp" / "server.py")


# ── async helpers ──────────────────────────────────────────────────────────────

async def _async_call_tool(script: str, env_extra: dict,
                            tool_name: str, arguments: dict) -> str:
    """Connect to an MCP server, call one tool, return text output."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    full_env = {**os.environ, **env_extra}
    params = StdioServerParameters(
        command="python",
        args=[script],
        env=full_env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            texts = [c.text for c in result.content if hasattr(c, "text")]
            return "\n".join(texts)


async def _async_list_tools(script: str, env_extra: dict) -> list[dict]:
    """Return tool schemas from an MCP server as Anthropic-compatible dicts."""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    full_env = {**os.environ, **env_extra}
    params = StdioServerParameters(
        command="python",
        args=[script],
        env=full_env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.inputSchema,
                }
                for t in result.tools
            ]


def _run_async(coro) -> Any:
    """Run a coroutine in a new event loop (safe to call from any thread)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — use a thread executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ── public API ─────────────────────────────────────────────────────────────────

def call_vault_tool(tool_name: str, arguments: dict) -> str:
    """Call a vault MCP server tool synchronously."""
    env = {"VAULT_PATH": str(VAULT_PATH)}
    try:
        return _run_async(_async_call_tool(VAULT_MCP_SCRIPT, env, tool_name, arguments))
    except Exception as e:
        logger.error(f"vault_tool '{tool_name}' failed: {e}")
        return f"Error calling vault tool '{tool_name}': {e}"


def call_gmail_tool(tool_name: str, arguments: dict) -> str:
    """Call a gmail MCP server tool synchronously."""
    env = {
        "VAULT_PATH": str(VAULT_PATH),
        "GMAIL_TOKEN_PATH": str(TOKEN_PATH),
    }
    try:
        return _run_async(_async_call_tool(GMAIL_MCP_SCRIPT, env, tool_name, arguments))
    except Exception as e:
        logger.error(f"gmail_tool '{tool_name}' failed: {e}")
        return f"Error calling gmail tool '{tool_name}': {e}"


def get_vault_tools() -> list[dict]:
    """Return vault MCP tool schemas (for Anthropic API)."""
    env = {"VAULT_PATH": str(VAULT_PATH)}
    try:
        return _run_async(_async_list_tools(VAULT_MCP_SCRIPT, env))
    except Exception as e:
        logger.error(f"Failed to fetch vault tools: {e}")
        return []


def get_gmail_tools() -> list[dict]:
    """Return gmail MCP tool schemas (for Anthropic API)."""
    env = {
        "VAULT_PATH": str(VAULT_PATH),
        "GMAIL_TOKEN_PATH": str(TOKEN_PATH),
    }
    try:
        return _run_async(_async_list_tools(GMAIL_MCP_SCRIPT, env))
    except Exception as e:
        logger.error(f"Failed to fetch gmail tools: {e}")
        return []


def get_all_tools() -> list[dict]:
    """Return all MCP tool schemas combined (vault + gmail)."""
    return get_vault_tools() + get_gmail_tools()


def dispatch_tool(tool_name: str, arguments: dict) -> str:
    """Route a tool call to the correct MCP server based on name prefix."""
    if tool_name.startswith("vault_"):
        return call_vault_tool(tool_name, arguments)
    elif tool_name in {
        "send_email", "draft_email", "search_emails",
        "get_email", "list_unread", "reply_email",
    }:
        return call_gmail_tool(tool_name, arguments)
    else:
        return f"Unknown tool: {tool_name!r}"
