"""Configuration management for Twitter scraper."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration class for Twitter scraper."""

    def __init__(self):
        self.username = os.getenv("USERNAME")
        self.password = os.getenv("PASSWORD")
        self.backup_code = os.getenv("BACKUP_CODE")

        # Paths
        self.save_path = Path("downloaded")
        self.session_path = Path("session")
        self.cookies_file = self.session_path / "cookies.json"
        self.screenshot_path = Path("screenshots")

        # Debug paths
        self.debug_path = Path("debug")
        self.debug_html_path = self.debug_path / "html"
        self.debug_screenshots_path = self.debug_path / "screenshots"

        # Selenium config - always headless
        self.headless = True
        self.remote_url = os.getenv("REMOTE_URL")

        # Debug config
        self.debug_mode = False  # Set programmatically via CLI

        # Scraping config
        self.login_wait = float(os.getenv("LOGIN_WAIT", "15.0"))
        self.scroll_delay = float(os.getenv("SCROLL_DELAY", "5.0"))
        self.max_error_count = int(os.getenv("MAX_ERROR_COUNT", "3"))

        # Twitter URLs
        self.front_page = "https://x.com"

        # Create directories if they don't exist
        self.save_path.mkdir(exist_ok=True)
        self.session_path.mkdir(exist_ok=True)
        self.screenshot_path.mkdir(exist_ok=True)

    def enable_debug(self) -> None:
        """Enable debug mode and create debug directories."""
        self.debug_mode = True
        self.debug_path.mkdir(exist_ok=True)
        self.debug_html_path.mkdir(exist_ok=True)
        self.debug_screenshots_path.mkdir(exist_ok=True)

    @property
    def likes_url(self) -> str:
        """Get the likes URL for the configured user."""
        return f"https://x.com/{self.username}/likes"

    def validate(self) -> list[str]:
        """Validate configuration and return list of missing items."""
        missing = []
        if not self.username:
            missing.append("USERNAME")
        if not self.password:
            missing.append("PASSWORD")
        return missing
