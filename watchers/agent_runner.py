"""
Agent Runner — AI Employee

Runs reasoning tasks through the Claude Code CLI (claude --print).
Uses your Claude Code subscription — no separate API charges.

Claude Code has the vault and gmail MCP servers configured in
~/.claude/settings.json, so it calls them automatically when given
instructions that reference vault_* or email tools.

Usage:
    from agent_runner import run_agent_task

    run_agent_task(
        prompt="Use vault_list_folder to check Needs_Action and process each item...",
        task_name="process_needs_action"
    )

Environment:
    CLAUDE_PATH   — path to the claude binary (default: claude)
    LOG_ONLY      — true = dry run, log only, no real actions
"""

import os
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("AgentRunner")

CLAUDE_BIN = os.getenv("CLAUDE_PATH", "claude")
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"
WATCHERS_DIR = Path(__file__).parent


def run_agent_task(prompt: str, task_name: str = "task") -> bool:
    """
    Run a reasoning task via Claude Code CLI.

    Claude Code uses your subscription (no API charges).
    It has access to the vault and gmail MCP servers configured in
    ~/.claude/settings.json, so it can call vault_* and gmail tools directly.

    Returns True on success, False on failure.
    """
    if DRY_RUN:
        logger.info(f"[DRY RUN] AgentRunner — task: {task_name}")
        logger.info(f"  Prompt: {prompt[:120]}...")
        return True

    cmd = [CLAUDE_BIN, "--print", "--dangerously-skip-permissions", prompt]
    logger.info(f"[AgentRunner] Starting task: {task_name}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(WATCHERS_DIR.parent),
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            logger.info(f"[AgentRunner] Task '{task_name}' complete")
            return True
        else:
            output = result.stderr[:500] or result.stdout[:500]
            logger.error(f"[AgentRunner] Task '{task_name}' failed (exit {result.returncode}): {output}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"[AgentRunner] Task '{task_name}' timed out after 5 minutes")
        return False
    except FileNotFoundError:
        logger.error(
            f"[AgentRunner] Claude binary not found: '{CLAUDE_BIN}'. "
            "Set CLAUDE_PATH in .env"
        )
        return False
