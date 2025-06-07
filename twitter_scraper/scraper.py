"""Image scraping functionality for Twitter."""

import base64
import io
import logging
import time
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
from selenium.common.exceptions import JavascriptException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from .config import Config
from .debug import DebugCapture

logger = logging.getLogger(__name__)

FETCH_IMG_TEMPLATE = """
return new Promise((resolve, reject) => {
    const toDataURL = url => fetch(url)
      .then(response => response.blob())
      .then(blob => new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onloadend = () => resolve(reader.result)
        reader.onerror = reject
        reader.readAsDataURL(blob)
      }))

    toDataURL('%%image-url%%')
      .then(dataUrl => resolve(dataUrl))
      .catch(err => reject(err));
});
"""


class TwitterImageScraper:
    """Handles Twitter image scraping functionality."""

    def __init__(self, driver: WebDriver, config: Config):
        self.driver = driver
        self.config = config
        self.debug_capture = DebugCapture(driver, config)

    def save_image_from_data_url(
        self, img_name: str, data_url: bytes, output_path: Path
    ) -> bool:
        """Save image from base64 data URL."""
        try:
            # Decode base64 data
            img_bytes = base64.b64decode(data_url.split(b",", 1)[1])

            # Open as PIL Image
            img = Image.open(io.BytesIO(img_bytes))

            # Determine output path
            output_file = output_path / f"{img_name}.{img.format.lower()}"

            # Check if file exists and compare sizes to avoid duplicates
            if output_file.exists():
                try:
                    existing_img = Image.open(output_file)
                    if len(existing_img.tobytes()) >= len(img.tobytes()):
                        logger.debug(
                            f"Image {output_file} already exists with same or larger size"
                        )
                        return True
                except Exception:
                    pass  # If we can't open existing file, overwrite it

            # Save image
            img.save(output_file)
            logger.info(f"Image saved: {output_file}")
            return True

        except Exception as e:
            logger.error(f"Failed to save image {img_name}: {e}")
            return False

    def fetch_image(self, img_url: str) -> bytes | None:
        """Fetch image data from URL using JavaScript."""
        try:
            logger.debug(f"Fetching image: {img_url}")
            result = self.driver.execute_script(
                FETCH_IMG_TEMPLATE.replace("%%image-url%%", img_url)
            )
            return result.encode("ascii") if result else None
        except JavascriptException as e:
            logger.warning(f"JavaScript error fetching {img_url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {img_url}: {e}")
            return None

    def get_image_name(self, img_element, url: str) -> str:
        """Generate unique image name from URL and tweet context."""
        try:
            # Extract image ID from URL
            parsed_url = urlparse(url)
            img_id = parsed_url.path.rsplit("/", 1)[-1]

            # Try to get tweet context for better naming
            try:
                tweet_link = img_element.find_element(
                    By.XPATH, "../../../.."
                ).get_attribute("href")
                if tweet_link:
                    path_parts = urlparse(tweet_link).path.split("/")
                    if len(path_parts) >= 5:
                        _, author, _, twitter_id, _ = path_parts[:5]
                        return f"{author}_{twitter_id}_{img_id}"
            except Exception:
                pass  # Fall back to simple naming

            return img_id

        except Exception as e:
            logger.warning(f"Error generating image name: {e}")
            return f"unknown_{int(time.time())}"

    def download_visible_images(
        self, max_error_count: int = 3
    ) -> tuple[object | None, set[str]]:
        """Download all visible images on current page."""
        self.debug_capture.log_action("Downloading visible images", "Starting image collection")
        self.debug_capture.capture_step("download_start", "Beginning to download visible images")

        imgs = self.driver.find_elements(By.XPATH, '//img[@alt="Image"]')
        self.debug_capture.log_action("Found images", f"Located {len(imgs)} images on page")

        last_img = None
        viewed_urls = set()

        for img in imgs:
            url = img.get_attribute("src")
            if not url:
                continue

            viewed_urls.add(url)

            # Skip thumbnail images
            if any(size in url for size in ["name=240x240", "name=360x360"]):
                continue
            else:
                last_img = img

            # Convert to high quality format
            url = self._enhance_image_url(url)
            logger.debug(f"Processing image: {url}")

            # Generate image name
            image_name = self.get_image_name(img, url)

            # Skip if already exists
            output_file = self.config.save_path / f"{image_name}.png"
            if output_file.exists():
                logger.debug(f"Image {output_file} already exists")
                continue

            # Download with retry logic
            error_count = 0
            while error_count < max_error_count:
                self.debug_capture.log_action("Downloading image", f"Fetching {image_name}")
                img_data = self.fetch_image(url)
                if img_data:
                    self.debug_capture.log_action("Image fetched", f"Successfully fetched {image_name}")
                    self.save_image_from_data_url(
                        image_name, img_data, self.config.save_path
                    )
                    break
                else:
                    error_count += 1
                    if error_count < max_error_count:
                        logger.warning(
                            f"Retry {error_count}/{max_error_count} for {url}"
                        )
                        self.debug_capture.log_action("Retry download", f"Attempt {error_count} for {image_name}")
                        time.sleep(2)
                    else:
                        logger.error(
                            f"Failed to download {url} after {max_error_count} attempts"
                        )
                        self.debug_capture.capture_error("download_failed", Exception(f"Failed to download {url}"))

        self.debug_capture.capture_step("download_complete", f"Completed downloading {len(viewed_urls)} images")
        return last_img, viewed_urls

    def _enhance_image_url(self, url: str) -> str:
        """Convert image URL to highest quality format."""
        return (
            url.replace("format=jpg", "format=png")
            .replace("format=webp", "format=png")
            .replace("name=small", "name=large")
            .replace("name=900x900", "name=large")
        )

    def scroll_and_download(
        self, max_scroll: int = 1000, max_error_count: int = 3
    ) -> int:
        """Scroll through timeline and download all images."""
        self.debug_capture.log_action("Starting scroll download", f"max_scroll={max_scroll}")

        logger.info(f"Navigating to: {self.config.likes_url}")
        self.debug_capture.log_action("Navigating to URL", self.config.likes_url)
        self.driver.get(self.config.likes_url)
        time.sleep(10)
        self.debug_capture.capture_step("page_loaded", f"Loaded {self.config.likes_url}")

        loop = 0
        previous_urls = set()
        total_downloaded = 0

        logger.info(f"Starting scroll download (max_scroll={max_scroll})")
        self.debug_capture.capture_step("scroll_start", f"Beginning scroll download with max_scroll={max_scroll}")

        while loop < max_scroll:
            logger.info(f"Scroll iteration: {loop + 1}/{max_scroll}")
            self.debug_capture.log_action("Scroll iteration", f"{loop + 1}/{max_scroll}")

            error_count = 0
            while error_count < max_error_count:
                try:
                    last_img, viewed_urls = self.download_visible_images(
                        max_error_count
                    )

                    logger.info(f"Found {len(viewed_urls)} images on page")
                    self.debug_capture.log_action("Images found", f"{len(viewed_urls)} images on current page")

                    # Check if we found new content
                    if len(viewed_urls.union(previous_urls)) == len(previous_urls):
                        logger.info("No new images found, reached end of timeline")
                        self.debug_capture.capture_step("timeline_end", "No new content found, reached end")
                        return total_downloaded

                    total_downloaded += len(viewed_urls - previous_urls)
                    previous_urls = viewed_urls
                    self.debug_capture.log_action("Progress update", f"Total downloaded: {total_downloaded}")
                    break

                except Exception as e:
                    error_count += 1
                    if error_count >= max_error_count:
                        logger.error(
                            f"Max errors reached in scroll iteration {loop}: {e}"
                        )
                        self.debug_capture.capture_error("max_errors_reached", e)
                        raise
                    logger.warning(
                        f"Error in scroll iteration {loop}, retry {error_count}: {e}"
                    )
                    self.debug_capture.capture_error("scroll_iteration_error", e)
                    time.sleep(5)

            # Scroll down
            if last_img:
                try:
                    self.debug_capture.log_action("Scrolling", f"Scrolling to next section in iteration {loop + 1}")
                    ActionChains(self.driver).scroll_to_element(last_img).perform()
                    time.sleep(self.config.scroll_delay)
                    self.debug_capture.capture_step(f"scroll_{loop + 1}", f"Scrolled down in iteration {loop + 1}")
                except Exception as e:
                    logger.warning(f"Scroll error: {e}")
                    self.debug_capture.capture_error("scroll_error", e)

            loop += 1

        logger.info(f"Completed scroll download: {total_downloaded} images processed")
        self.debug_capture.capture_step("scroll_complete", f"Completed all {loop} scroll iterations, {total_downloaded} images processed")
        self.debug_capture.create_debug_summary()
        return total_downloaded
