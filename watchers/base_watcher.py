"""Base watcher template for all AI Employee watchers."""

import time
import json
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class BaseWatcher(ABC):
    """Abstract base class for all watcher implementations."""

    def __init__(self, vault_path: str, check_interval: int = 60):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / "Needs_Action"
        self.logs_dir = self.vault_path / "Logs"
        self.check_interval = check_interval
        self.logger = logging.getLogger(self.__class__.__name__)

        # Ensure directories exist
        self.needs_action.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create .md file in Needs_Action folder."""
        pass

    def log_action(self, action_type: str, target: str, result: str, details: dict | None = None):
        """Log an action to the vault's Logs directory."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": action_type,
            "actor": self.__class__.__name__,
            "target": target,
            "result": result,
            "details": details or {},
        }

        log_file = self.logs_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"

        # Append to daily log file
        entries = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text())
            except (json.JSONDecodeError, ValueError):
                entries = []

        entries.append(log_entry)
        log_file.write_text(json.dumps(entries, indent=2))
        self.logger.info(f"Logged: {action_type} -> {target} [{result}]")

    def run(self):
        """Main loop - check for updates and create action files."""
        self.logger.info(f"Starting {self.__class__.__name__}")
        while True:
            try:
                items = self.check_for_updates()
                for item in items:
                    filepath = self.create_action_file(item)
                    self.log_action(
                        action_type="file_detected",
                        target=str(filepath),
                        result="success",
                        details={"item": str(item)},
                    )
                    self.logger.info(f"Created action file: {filepath}")
            except KeyboardInterrupt:
                self.logger.info("Watcher stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Error in watcher loop: {e}")
                self.log_action(
                    action_type="watcher_error",
                    target=self.__class__.__name__,
                    result="error",
                    details={"error": str(e)},
                )
            time.sleep(self.check_interval)
