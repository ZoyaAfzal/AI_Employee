"""
LinkedIn Poster — Silver Tier

Posts business content to LinkedIn via Playwright.
Used by the linkedin-poster skill and the orchestrator's scheduled posting.

Usage (standalone):
    python linkedin_poster.py --content "Your post text here" --hashtags "#AI #Business"
    python linkedin_poster.py --file /path/to/post_content.txt
    python linkedin_poster.py --from-vault   # reads from AI_Employee_Vault/Approved/

Called by orchestrator:
    from linkedin_poster import LinkedInPoster
    poster = LinkedInPoster(vault_path)
    result = poster.post("Your content", hashtags=["#AI", "#Business"])
"""

import os
import sys
import re
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

# ── config ─────────────────────────────────────────────────────────────────────
SESSION_DIR = Path(__file__).parent / "sessions" / "linkedin"
VAULT_PATH = Path(__file__).parent.parent / "AI_Employee_Vault"
DRY_RUN = os.getenv("LOG_ONLY", "false").lower() == "true"

MAX_POST_LENGTH = 3000      # LinkedIn character limit
POSTS_PER_DAY_LIMIT = 2     # Company Handbook limit


class LinkedInPoster:
    """Posts content to LinkedIn using a persistent Playwright session."""

    def __init__(self, vault_path: str | Path | None = None):
        self.vault_path = Path(vault_path) if vault_path else VAULT_PATH
        self.logs_dir = self.vault_path / "Logs"
        self.pending_dir = self.vault_path / "Pending_Approval"
        self.approved_dir = self.vault_path / "Approved"
        self.done_dir = self.vault_path / "Done"
        self.logger = logging.getLogger("LinkedInPoster")
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        if DRY_RUN:
            self.logger.warning("DRY RUN MODE — no posts will be published")

    # ── public API ─────────────────────────────────────────────────────────────

    def post(self, content: str, hashtags: list[str] | None = None) -> dict:
        """
        Post content to LinkedIn.

        Returns:
            {"success": bool, "url": str, "error": str | None}
        """
        # Compose full post text
        post_text = self._compose(content, hashtags or [])

        if len(post_text) > MAX_POST_LENGTH:
            self.logger.warning(
                f"Post length {len(post_text)} exceeds {MAX_POST_LENGTH}. Truncating."
            )
            post_text = post_text[: MAX_POST_LENGTH - 3] + "..."

        if DRY_RUN:
            self.logger.info(f"[DRY RUN] Would post ({len(post_text)} chars):\n{post_text[:200]}…")
            self._log_post("dry_run", post_text)
            return {"success": True, "url": "dry_run", "error": None}

        headed = os.getenv("LINKEDIN_HEADED", "false").lower() == "true"
        return self._do_post(post_text, headed=headed)

    def post_from_approval_file(self, approval_file: Path) -> dict:
        """Read content from an approved LinkedIn approval file and post it."""
        try:
            raw = approval_file.read_text(encoding="utf-8")
            # Extract the post preview block between the ## Post Preview heading and the next ##
            match = re.search(
                r"##\s+Post Preview\s*\n+(.*?)(?=\n##|\Z)", raw, re.DOTALL
            )
            if not match:
                return {"success": False, "url": None, "error": "No post content found in approval file"}
            content = match.group(1).strip()
        except Exception as e:
            return {"success": False, "url": None, "error": str(e)}

        return self.post(content)

    def process_approved_posts(self):
        """
        Scan /Approved/ for pending LinkedIn post approvals and publish them.
        Called by the orchestrator.
        """
        if not self.approved_dir.exists():
            return

        pattern = "LINKEDIN_*.md"
        approved_files = list(self.approved_dir.glob(pattern))

        if not approved_files:
            self.logger.debug("No approved LinkedIn posts found")
            return

        self.logger.info(f"Found {len(approved_files)} approved LinkedIn post(s)")

        for approval_file in approved_files:
            self.logger.info(f"Processing approved post: {approval_file.name}")
            result = self.post_from_approval_file(approval_file)

            if result["success"]:
                # Move approval file to Done
                done_path = self.done_dir / approval_file.name
                approval_file.rename(done_path)
                self.logger.info(f"Moved to Done: {approval_file.name}")
            else:
                self.logger.error(
                    f"Failed to post {approval_file.name}: {result['error']}"
                )

    # ── browser automation ─────────────────────────────────────────────────────

    def _do_post(self, post_text: str, headed: bool = False) -> dict:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return {
                "success": False,
                "url": None,
                "error": "Playwright not installed. Run: uv add playwright && playwright install chromium",
            }

        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                str(SESSION_DIR),
                headless=not headed,
                slow_mo=100 if headed else 0,
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                return self._browser_post(page, post_text)
            finally:
                ctx.close()

    def _browser_post(self, page, post_text: str) -> dict:
        """Navigate LinkedIn and submit the post."""
        try:
            # Go to feed
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded",
                      timeout=20000)
            page.wait_for_timeout(3000)

            # Check if we're logged in
            if "login" in page.url or "authwall" in page.url:
                return {
                    "success": False,
                    "url": None,
                    "error": (
                        "Not logged in to LinkedIn. "
                        "Run linkedin_watcher.py with LINKEDIN_FIRST_LOGIN=true to set up session."
                    ),
                }

            # Save debug screenshot of the feed so we can inspect the page state
            headed = os.getenv("LINKEDIN_HEADED", "false").lower() == "true"
            if headed:
                try:
                    dbg_dir = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs" / "screenshots"
                    dbg_dir.mkdir(parents=True, exist_ok=True)
                    dbg_path = dbg_dir / "debug_feed.png"
                    page.screenshot(path=str(dbg_path), full_page=False)
                    self.logger.info(f"Debug screenshot saved: {dbg_path}")
                except Exception:
                    pass

            # Stay on feed and click "Start a post" button
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded",
                      timeout=20000)
            page.wait_for_timeout(3000)

            # In headed/debug mode — log contenteditable/placeholder divs (the real "Start a post")
            if headed:
                try:
                    divs_info = page.evaluate("""
                        () => [...document.querySelectorAll('div[contenteditable], div[aria-placeholder], div[data-placeholder]')]
                            .filter(el => el.offsetParent !== null)
                            .map(el => ({
                                tag: el.tagName,
                                ariaPlaceholder: el.getAttribute('aria-placeholder'),
                                dataPlaceholder: el.getAttribute('data-placeholder'),
                                contenteditable: el.getAttribute('contenteditable'),
                                className: el.className.slice(0, 80),
                                text: el.innerText.trim().slice(0, 60)
                            }))
                    """)
                    self.logger.info("=== Contenteditable/placeholder divs on feed ===")
                    for d in divs_info:
                        self.logger.info(f"  {d}")
                    self.logger.info("================================================")
                except Exception:
                    pass

            # "Start a post" is a div/placeholder, not a <button> — use JS to find it
            clicked = False
            try:
                result = page.evaluate("""
                    () => {
                        // 1. aria-placeholder on contenteditable divs
                        const byPlaceholder = document.querySelector(
                            'div[aria-placeholder*="post" i], div[data-placeholder*="post" i]'
                        );
                        if (byPlaceholder) { byPlaceholder.click(); return 'aria-placeholder'; }

                        // 2. Any element whose visible text is exactly "Start a post"
                        const all = [...document.querySelectorAll('*')];
                        const byText = all.find(el =>
                            el.children.length === 0 &&
                            el.innerText &&
                            el.innerText.trim().toLowerCase() === 'start a post'
                        );
                        if (byText) { byText.click(); return 'innerText'; }

                        // 3. Share box trigger class
                        const trigger = document.querySelector(
                            '.share-box-feed-entry__trigger, ' +
                            '[class*="share-box-feed-entry__trigger"]'
                        );
                        if (trigger) { trigger.click(); return 'trigger-class'; }

                        return null;
                    }
                """)
                if result:
                    self.logger.info(f"Clicked 'Start a post' via JS ({result})")
                    clicked = True
            except Exception as e:
                self.logger.warning(f"JS click attempt failed: {e}")

            if not clicked:
                try:
                    dbg_dir = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs" / "screenshots"
                    dbg_dir.mkdir(parents=True, exist_ok=True)
                    dbg_path2 = dbg_dir / "debug_no_button.png"
                    page.screenshot(path=str(dbg_path2), full_page=True)
                    self.logger.error(f"Could not find button. Full-page screenshot: {dbg_path2}")
                except Exception:
                    pass
                return {
                    "success": False,
                    "url": None,
                    "error": "Could not find 'Start a post' button. Check debug_no_button.png in Logs/screenshots/",
                }

            # Wait for the modal / share dialog to fully open
            page.wait_for_timeout(2500)

            # Find the text area in the post modal — ordered by likelihood
            textarea_selectors = [
                "div.ql-editor[contenteditable='true']",
                "div[role='textbox'][contenteditable='true']",
                ".share-creation-state__editor div[contenteditable='true']",
                "div[contenteditable='true'][data-placeholder]",
                "[aria-label='Text editor for creating content']",
                "div[contenteditable='true']",
                ".ql-editor",
            ]

            textarea = None
            for sel in textarea_selectors:
                try:
                    el = page.wait_for_selector(sel, timeout=5000, state="visible")
                    if el and el.is_visible():
                        textarea = el
                        self.logger.info(f"Found textarea with selector: {sel}")
                        break
                except Exception:
                    continue

            if not textarea:
                return {
                    "success": False,
                    "url": None,
                    "error": "Could not find post text area. LinkedIn UI may have changed.",
                }

            # Type the post content
            textarea.click()
            page.wait_for_timeout(500)

            # Use keyboard.type for content with special characters
            page.keyboard.type(post_text, delay=30)
            page.wait_for_timeout(1500)

            # Click the Post button
            post_button_selectors = [
                "button.share-actions__primary-action",
                "button[class*='share-actions__primary']",
                "button[aria-label='Post']",
                "button:has-text('Post')",
                ".share-box__actions button.artdeco-button--primary",
                "div.share-box_actions button[class*='primary']",
            ]

            posted = False
            for sel in post_button_selectors:
                try:
                    btn = page.wait_for_selector(sel, timeout=5000, state="visible")
                    if btn and btn.is_enabled():
                        btn.click()
                        posted = True
                        break
                except Exception:
                    continue

            if not posted:
                # Last resort: find any enabled primary button in the modal
                try:
                    btn = page.locator("button.artdeco-button--primary").last
                    if btn.is_enabled():
                        btn.click()
                        posted = True
                except Exception:
                    pass

            if not posted:
                return {
                    "success": False,
                    "url": None,
                    "error": "Could not click Post button.",
                }

            # Wait for LinkedIn to process the post
            page.wait_for_timeout(4000)

            # Check for error dialogs before declaring success
            error_texts = [
                "unable to complete your request",
                "please try again",
                "something went wrong",
                "error posting",
                "couldn't post",
            ]
            page_text = page.inner_text("body").lower()
            for err in error_texts:
                if err in page_text:
                    # Take screenshot of the error for debugging
                    try:
                        screenshot_dir = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs" / "screenshots"
                        screenshot_dir.mkdir(parents=True, exist_ok=True)
                        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
                        err_path = screenshot_dir / f"linkedin_error_{ts}.png"
                        page.screenshot(path=str(err_path), full_page=False)
                        self.logger.warning(f"Error screenshot saved: {err_path}")
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "url": None,
                        "error": f"LinkedIn rejected the post: '{err}'. This is usually rate-limiting — wait 15–30 minutes before posting again.",
                    }

            post_url = page.url

            # Take screenshot as audit proof (isolated so a failure here never blocks success)
            screenshot_name = None
            try:
                screenshot_dir = Path(__file__).parent.parent / "AI_Employee_Vault" / "Logs" / "screenshots"
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
                screenshot_path = screenshot_dir / f"linkedin_post_{ts}.png"
                page.screenshot(path=str(screenshot_path), full_page=False)
                screenshot_name = str(screenshot_path.name)
                self.logger.info(f"Screenshot saved: {screenshot_path}")
            except Exception as ss_err:
                self.logger.warning(f"Screenshot failed (post still succeeded): {ss_err}")

            self._log_post("success", post_text, screenshot=screenshot_name or "not_saved")
            self.logger.info(f"Posted successfully to LinkedIn ({len(post_text)} chars)")

            return {"success": True, "url": post_url, "error": None}

        except Exception as e:
            self.logger.error(f"LinkedIn post failed: {e}")
            self._log_post("error", post_text, error=str(e))
            return {"success": False, "url": None, "error": str(e)}

    # ── helpers ────────────────────────────────────────────────────────────────

    def _compose(self, content: str, hashtags: list[str]) -> str:
        """Combine content and hashtags into a single post string."""
        text = content.strip()
        if hashtags:
            tag_line = " ".join(
                t if t.startswith("#") else f"#{t}" for t in hashtags
            )
            text = f"{text}\n\n{tag_line}"
        return text

    def _log_post(self, result: str, content: str, **extras):
        """Append to the vault's daily JSON log."""
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.logs_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_type": "linkedin_post",
            "actor": "LinkedInPoster",
            "target": "linkedin.com",
            "result": result,
            "details": {
                "content_preview": content[:100],
                "char_count": len(content),
                **extras,
            },
        }

        entries = []
        if log_file.exists():
            try:
                entries = json.loads(log_file.read_text())
            except Exception:
                entries = []
        entries.append(entry)
        log_file.write_text(json.dumps(entries, indent=2))


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Load .env
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())

    parser = argparse.ArgumentParser(description="Post to LinkedIn")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--content", help="Post text")
    group.add_argument("--file", help="Path to file containing post text")
    group.add_argument(
        "--from-vault",
        action="store_true",
        help="Process all LINKEDIN_*.md files in /Approved/",
    )
    parser.add_argument(
        "--hashtags",
        nargs="*",
        default=[],
        help="Hashtags to append (with or without # prefix)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show browser window (useful for debugging)",
    )
    args = parser.parse_args()

    if args.headed:
        os.environ["LINKEDIN_HEADED"] = "true"

    vault_path = os.getenv("VAULT_PATH", str(Path(__file__).parent.parent / "AI_Employee_Vault"))
    poster = LinkedInPoster(vault_path)

    if args.from_vault:
        poster.process_approved_posts()
    elif args.file:
        content = Path(args.file).read_text(encoding="utf-8")
        result = poster.post(content, hashtags=args.hashtags)
        print(f"Result: {result}")
    else:
        result = poster.post(args.content, hashtags=args.hashtags)
        print(f"Result: {result}")


if __name__ == "__main__":
    main()
