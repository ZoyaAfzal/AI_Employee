"""File System Watcher - monitors /Inbox for new files and creates action items in /Needs_Action."""

import sys
import time
import shutil
import logging
from pathlib import Path
from datetime import datetime, timezone

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add parent to path for base_watcher import
sys.path.insert(0, str(Path(__file__).parent))
from base_watcher import BaseWatcher


class InboxHandler(FileSystemEventHandler):
    """Handles new files dropped into the /Inbox folder."""

    def __init__(self, watcher: "FileSystemWatcher"):
        super().__init__()
        self.watcher = watcher

    # Windows system / temp files to always ignore
    _SKIP_NAMES = {"desktop.ini", "thumbs.db", "thumbs.db:encryptable"}
    _SKIP_PREFIXES = (".", "~", "$", "~$")

    def on_created(self, event):
        if event.is_directory:
            return

        source = Path(event.src_path)

        # Skip hidden, temp, and Windows system files
        name_lower = source.name.lower()
        if (
            name_lower in self._SKIP_NAMES
            or any(source.name.startswith(p) for p in self._SKIP_PREFIXES)
        ):
            return

        # Wait briefly for the file to be fully written (race condition guard)
        for _ in range(5):
            if source.exists() and source.stat().st_size >= 0:
                break
            time.sleep(0.2)
        else:
            self.watcher.logger.debug(f"File disappeared before processing: {source.name}")
            return

        self.watcher.logger.info(f"New file detected: {source.name}")
        self.watcher.process_new_file(source)


class FileSystemWatcher(BaseWatcher):
    """Watches the /Inbox folder for new files and creates action items."""

    def __init__(self, vault_path: str):
        super().__init__(vault_path, check_interval=5)
        self.inbox = self.vault_path / "Inbox"
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.processed_files: set[str] = set()
        self.observer = Observer()

    def check_for_updates(self) -> list:
        """Scan Inbox for any unprocessed files (fallback for watchdog)."""
        new_files = []
        if self.inbox.exists():
            for f in self.inbox.iterdir():
                if f.is_file() and f.name not in self.processed_files and not f.name.startswith("."):
                    new_files.append(f)
        return new_files

    def create_action_file(self, item: Path) -> Path:
        """Create a metadata .md file in /Needs_Action for the given file."""
        return self.process_new_file(item)

    def process_new_file(self, source: Path) -> Path:
        """Process a new file: copy to Needs_Action and create metadata."""
        if source.name in self.processed_files:
            return self.needs_action / f"FILE_{source.name}"

        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

        # Copy the original file to Needs_Action
        dest_file = self.needs_action / f"FILE_{source.name}"
        if not dest_file.exists():
            if not source.exists():
                self.logger.warning(f"Source file gone before copy: {source.name}")
                return dest_file
            shutil.copy2(source, dest_file)

        # Create metadata markdown file
        file_size = source.stat().st_size
        file_ext = source.suffix.lower()
        file_type = self._categorize_file(file_ext)

        meta_path = self.needs_action / f"FILE_{source.stem}_{timestamp}.md"
        meta_content = f"""---
type: file_drop
original_name: {source.name}
size: {file_size}
file_type: {file_type}
extension: {file_ext}
received: {now.isoformat()}
priority: normal
status: pending
---

## New File Received

**File:** {source.name}
**Size:** {self._format_size(file_size)}
**Type:** {file_type}
**Received:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}

## Suggested Actions
- [ ] Review file contents
- [ ] Categorize and tag appropriately
- [ ] Process according to file type
- [ ] Move to /Done when complete
"""
        meta_path.write_text(meta_content)
        self.processed_files.add(source.name)

        self.log_action(
            action_type="file_inbox_processed",
            target=source.name,
            result="success",
            details={
                "original_name": source.name,
                "size": file_size,
                "file_type": file_type,
                "meta_file": str(meta_path.name),
            },
        )

        self.logger.info(f"Processed: {source.name} -> {meta_path.name}")
        return meta_path

    def _categorize_file(self, ext: str) -> str:
        """Categorize a file based on its extension."""
        categories = {
            "document": [".pdf", ".doc", ".docx", ".txt", ".md", ".rtf", ".odt"],
            "spreadsheet": [".xls", ".xlsx", ".csv", ".ods"],
            "image": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"],
            "data": [".json", ".xml", ".yaml", ".yml", ".toml"],
            "code": [".py", ".js", ".ts", ".html", ".css", ".java", ".cpp"],
            "archive": [".zip", ".tar", ".gz", ".rar", ".7z"],
        }
        for category, extensions in categories.items():
            if ext in extensions:
                return category
        return "other"

    def _format_size(self, size: int) -> str:
        """Format file size to human readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def run(self):
        """Run the filesystem watcher using watchdog observer."""
        self.logger.info(f"Starting FileSystem Watcher on: {self.inbox}")
        self.logger.info(f"Action files will be created in: {self.needs_action}")

        # Process any existing files in Inbox first
        existing = self.check_for_updates()
        for item in existing:
            self.create_action_file(item)
            self.logger.info(f"Processed existing file: {item.name}")

        # Set up watchdog observer for real-time monitoring
        handler = InboxHandler(self)
        self.observer.schedule(handler, str(self.inbox), recursive=False)
        self.observer.start()

        self.logger.info("Watcher is running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Stopping watcher...")
            self.observer.stop()
        self.observer.join()
        self.logger.info("Watcher stopped.")


def main():
    """Entry point for the filesystem watcher."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
        ],
    )

    # Default vault path - adjust as needed
    vault_path = str(Path(__file__).parent.parent / "AI_Employee_Vault")

    # Allow override via command line argument
    if len(sys.argv) > 1:
        vault_path = sys.argv[1]

    logger = logging.getLogger("main")
    logger.info(f"Vault path: {vault_path}")

    watcher = FileSystemWatcher(vault_path)
    watcher.run()


if __name__ == "__main__":
    main()
