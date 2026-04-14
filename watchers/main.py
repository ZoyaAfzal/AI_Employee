"""
AI Employee — Main Entry Point (Silver Tier)

Starts the full orchestrator which runs:
  - FileSystem Watcher (Inbox folder monitoring)
  - Gmail Watcher     (unread important emails)
  - LinkedIn Watcher  (messages, connections, notifications)
  - Scheduled tasks   (daily briefing, weekly CEO briefing, LinkedIn posting)
  - Approval monitor  (/Approved and /Rejected folder polling)

Usage:
    cd watchers
    uv run python main.py

    # Or with options:
    ENABLE_GMAIL=false python main.py    # skip Gmail (no credentials yet)
    ENABLE_LINKEDIN=false python main.py # skip LinkedIn
    LOG_ONLY=true python main.py         # dry-run, no vault writes

First-time setup:
    1. Copy ../.env.example to ../.env and fill in credentials
    2. Run: python gmail_auth.py         (Gmail OAuth setup)
    3. Run: LINKEDIN_FIRST_LOGIN=true python linkedin_watcher.py  (LinkedIn session)
    4. Run: python main.py               (start everything)
"""

import os
import sys
import logging
from pathlib import Path

# ── load .env early so all modules pick up the env vars ───────────────────────
def _load_env():
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        loaded = 0
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
                loaded += 1
        print(f"[main] Loaded {loaded} variables from .env")
    else:
        print(f"[main] No .env file found at {env_file}. Using defaults / system env vars.")


_load_env()

# ── ensure logs dir exists ─────────────────────────────────────────────────────
logs_dir = Path(__file__).parent.parent / "logs"
logs_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(logs_dir / "ai_employee.log"), mode="a"),
    ],
)

logger = logging.getLogger("main")


def main():
    logger.info("=" * 60)
    logger.info("AI Employee — Silver Tier")
    logger.info("=" * 60)
    logger.info("Starting orchestrator...")

    # Import here so .env is loaded first
    sys.path.insert(0, str(Path(__file__).parent))
    from orchestrator import Orchestrator
    import signal

    orch = Orchestrator()
    signal.signal(signal.SIGINT, orch.shutdown)
    signal.signal(signal.SIGTERM, orch.shutdown)
    orch.run()


if __name__ == "__main__":
    main()
