"""Debug utilities for capturing screenshots and HTML source."""

import logging
from datetime import datetime

from selenium.webdriver.remote.webdriver import WebDriver

from .config import Config

logger = logging.getLogger(__name__)


class DebugCapture:
    """Handles debug capture functionality for screenshots and HTML source."""

    def __init__(self, driver: WebDriver, config: Config):
        self.driver = driver
        self.config = config
        self.step_counter = 0

    def capture_step(self, step_name: str, description: str = "") -> None:
        """Capture screenshot and HTML for a debug step."""
        if not self.config.debug_mode:
            return

        self.step_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        step_prefix = f"{self.step_counter:03d}_{timestamp}_{step_name}"

        try:
            # Capture screenshot
            self._capture_screenshot(step_prefix, description)

            # Capture HTML source
            self._capture_html(step_prefix, description)

            logger.debug(f"Debug capture completed for step: {step_name}")

        except Exception as e:
            logger.warning(f"Failed to capture debug information for {step_name}: {e!r}")

    def capture_error(self, error_name: str, exception: Exception) -> None:
        """Capture debug information when an error occurs."""
        if not self.config.debug_mode:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_prefix = f"ERROR_{timestamp}_{error_name}"
        description = f"Error occurred: {exception!r}"

        try:
            self._capture_screenshot(error_prefix, description)
            self._capture_html(error_prefix, description)

            logger.error(f"Debug error capture completed for: {error_name}")

        except Exception as e:
            logger.warning(f"Failed to capture error debug info for {error_name}: {e!r}")

    def _capture_screenshot(self, prefix: str, description: str) -> None:
        """Capture and save screenshot."""
        try:
            screenshot_path = self.config.debug_screenshots_path / f"{prefix}.png"
            self.driver.save_screenshot(str(screenshot_path))

            # Also save a metadata file with description
            meta_path = self.config.debug_screenshots_path / f"{prefix}_meta.txt"
            with meta_path.open("w") as f:
                f.write(f"Step: {prefix}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"Description: {description}\n")
                f.write(f"URL: {self.driver.current_url}\n")
                f.write(f"Page Title: {self.driver.title}\n")

            logger.debug(f"Screenshot saved: {screenshot_path}")

        except Exception as e:
            logger.warning(f"Failed to capture screenshot: {e!r}")

    def _capture_html(self, prefix: str, description: str) -> None:
        """Capture and save HTML source."""
        try:
            html_path = self.config.debug_html_path / f"{prefix}.html"

            # Get page source
            page_source = self.driver.page_source

            # Create enhanced HTML with debug info
            debug_html = f"""<!DOCTYPE html>
<!-- Debug capture for: {prefix} -->
<!-- Timestamp: {datetime.now().isoformat()} -->
<!-- Description: {description} -->
<!-- URL: {self.driver.current_url} -->
<!-- Page Title: {self.driver.title} -->

{page_source}
"""

            with html_path.open("w", encoding="utf-8") as f:
                f.write(debug_html)

            logger.debug(f"HTML source saved: {html_path}")

        except Exception as e:
            logger.warning(f"Failed to capture HTML source: {e!r}")

    def log_action(self, action: str, details: str = "") -> None:
        """Log an action being performed (when debug mode is on)."""
        if self.config.debug_mode:
            logger.info(f"[DEBUG] {action}: {details}")

    def capture_element_info(self, step_name: str, element_xpath: str) -> None:
        """Capture information about a specific element."""
        if not self.config.debug_mode:
            return

        try:
            from selenium.common.exceptions import NoSuchElementException
            from selenium.webdriver.common.by import By

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            info_path = self.config.debug_html_path / f"{timestamp}_{step_name}_element_info.txt"

            with info_path.open("w") as f:
                f.write(f"Element Debug Info - {step_name}\n")
                f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                f.write(f"XPath: {element_xpath}\n")
                f.write(f"Current URL: {self.driver.current_url}\n\n")

                try:
                    element = self.driver.find_element(By.XPATH, element_xpath)
                    f.write("Element found: Yes\n")
                    f.write(f"Element tag: {element.tag_name}\n")
                    f.write(f"Element text: {element.text}\n")
                    f.write(f"Element displayed: {element.is_displayed()}\n")
                    f.write(f"Element enabled: {element.is_enabled()}\n")
                    f.write(f"Element location: {element.location}\n")
                    f.write(f"Element size: {element.size}\n")

                    # Get all attributes
                    f.write("\nElement attributes:\n")
                    script = "return arguments[0].attributes;"
                    attributes = self.driver.execute_script(script, element)
                    for attr in attributes:
                        f.write(f"  {attr['name']}: {attr['value']}\n")

                except NoSuchElementException:
                    f.write("Element found: No\n")

                    # Try to find similar elements
                    f.write("\nSimilar elements on page:\n")
                    try:
                        # Extract the text from xpath for similar search
                        if "text()=" in element_xpath:
                            text_part = element_xpath.split("text()=")[1].strip("']\"")
                            similar_elements = self.driver.find_elements(By.XPATH, f"//*[contains(text(), '{text_part}')]")
                            for i, elem in enumerate(similar_elements[:10]):  # Limit to 10
                                f.write(f"  {i+1}. {elem.tag_name}: {elem.text[:100]}...\n")
                    except Exception:
                        pass

            logger.debug(f"Element info saved: {info_path}")

        except Exception as e:
            logger.warning(f"Failed to capture element info: {e!r}")

    def create_debug_summary(self) -> None:
        """Create a summary of all debug captures."""
        if not self.config.debug_mode:
            return

        try:
            summary_path = self.config.debug_path / "debug_summary.txt"

            with summary_path.open("w") as f:
                f.write("Lyubitori Debug Session Summary\n")
                f.write("=" * 40 + "\n")
                f.write(f"Session started: {datetime.now().isoformat()}\n")
                f.write(f"Total debug steps: {self.step_counter}\n\n")

                # List all screenshots
                f.write("Screenshots captured:\n")
                for screenshot in sorted(self.config.debug_screenshots_path.glob("*.png")):
                    f.write(f"  - {screenshot.name}\n")

                f.write("\nHTML sources captured:\n")
                for html_file in sorted(self.config.debug_html_path.glob("*.html")):
                    f.write(f"  - {html_file.name}\n")

                f.write(f"\nDebug files location: {self.config.debug_path}\n")

            logger.info(f"Debug summary created: {summary_path}")

        except Exception as e:
            logger.warning(f"Failed to create debug summary: {e!r}")
