"""WebDriver management for Twitter scraper."""

import logging

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.remote.webdriver import WebDriver

from .config import Config

logger = logging.getLogger(__name__)


class DriverManager:
    """Manages WebDriver lifecycle and configuration."""

    def __init__(self, config: Config):
        self.config = config
        self.driver: WebDriver | None = None

    def create_driver(self) -> WebDriver:
        """Create and configure Chrome WebDriver."""
        chrome_options = ChromeOptions()

        # Basic options
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--enable-automation")
        chrome_options.add_argument("--enable-file-cookies")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")

        # Headless mode
        if self.config.headless:
            chrome_options.add_argument("--headless")

        # User data directory for session persistence
        user_data_dir = self.config.session_path / "chrome_profile"
        user_data_dir.mkdir(exist_ok=True)
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")

        try:
            if self.config.remote_url:
                self.driver = webdriver.Remote(
                    self.config.remote_url, options=chrome_options, keep_alive=True
                )
            else:
                self.driver = webdriver.Chrome(options=chrome_options)

            # Configure window and timeouts
            self.driver.set_window_size(1920, 1080)
            self.driver.set_page_load_timeout(60)

            logger.info("WebDriver created successfully")
            return self.driver

        except Exception as e:
            logger.error(f"Failed to create WebDriver: {e}")
            raise

    def get_driver(self) -> WebDriver:
        """Get current driver or create new one."""
        if self.driver is None:
            self.driver = self.create_driver()
        return self.driver

    def quit_driver(self) -> None:
        """Quit WebDriver if it exists."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver quit successfully")
            except Exception as e:
                logger.warning(f"Error quitting WebDriver: {e}")
            finally:
                self.driver = None
