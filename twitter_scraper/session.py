"""Session and cookie management for Twitter scraper."""

import json
import logging
from pathlib import Path

from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages browser sessions and cookie persistence."""

    def __init__(self, session_path: Path):
        self.session_path = session_path
        self.cookies_file = session_path / "cookies.json"

    def save_cookies(self, driver: WebDriver) -> bool:
        """Save current browser cookies to file."""
        try:
            cookies = driver.get_cookies()
            with self.cookies_file.open("w") as f:
                json.dump(cookies, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(cookies)} cookies to {self.cookies_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save cookies: {e}")
            return False

    def load_cookies(self, driver: WebDriver) -> bool:
        """Load cookies from file into browser."""
        if not self.cookies_file.exists():
            logger.info("No saved cookies found")
            return False

        try:
            # First navigate to Twitter to set domain context
            driver.get("https://twitter.com")

            with self.cookies_file.open() as f:
                cookies = json.load(f)

            for cookie in cookies:
                try:
                    # Remove problematic fields that might cause issues
                    cookie.pop("sameSite", None)
                    cookie.pop("staleAt", None)
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(
                        f"Failed to add cookie {cookie.get('name', 'unknown')}: {e}"
                    )

            driver.refresh()
            logger.info(f"Loaded {len(cookies)} cookies from {self.cookies_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load cookies: {e}")
            return False

    def clear_session(self) -> bool:
        """Clear saved session data."""
        try:
            if self.cookies_file.exists():
                self.cookies_file.unlink()
                logger.info("Cleared saved session")
            return True
        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            return False

    def has_saved_session(self) -> bool:
        """Check if saved session exists."""
        return self.cookies_file.exists() and self.cookies_file.stat().st_size > 0
