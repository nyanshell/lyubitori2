"""Authentication module for Twitter login."""

import logging
import random
import time

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.ui import WebDriverWait

from .config import Config
from .debug import DebugCapture
from .session import SessionManager

logger = logging.getLogger(__name__)


class TwitterAuth:
    """Handles Twitter authentication and session management."""

    def __init__(
        self, driver: WebDriver, config: Config, session_manager: SessionManager
    ):
        self.driver = driver
        self.config = config
        self.session_manager = session_manager
        self.wait = WebDriverWait(driver, 10)
        self.debug_capture = DebugCapture(driver, config)

    def is_logged_in(self) -> bool:
        """Check if user is currently logged in to Twitter."""
        try:
            self.debug_capture.log_action("Checking login status", "Navigating to X.com")
            self.driver.get("https://x.com")
            time.sleep(3)
            self.debug_capture.capture_step("login_check", "Checking if user is logged in")

            # Look for elements that indicate we're logged in
            login_indicators = [
                '//*[contains(text(), "What\'s happening?")]',
                "//div[@data-testid='SideNav_NewTweet_Button']",
                "//div[@data-testid='primaryColumn']",
                "//a[@href='/compose/tweet']",
                "//span[text()='Home']",
            ]

            for xpath in login_indicators:
                try:
                    self.driver.find_element(By.XPATH, xpath)
                    logger.info("User is logged in")
                    return True
                except NoSuchElementException:
                    continue

            # Check if we're on login page or main page with sign in
            login_page_indicators = [
                "//*[text()='Phone, email, or username']",
                "//span[text()='Sign in']",
                "//a[contains(@href, '/login')]",
                "//input[@name='text']", # username input
            ]

            for xpath in login_page_indicators:
                try:
                    self.driver.find_element(By.XPATH, xpath)
                    logger.info("User is not logged in")
                    return False
                except NoSuchElementException:
                    continue

            logger.warning("Login status unclear")
            return False

        except Exception as e:
            logger.error(f"Error checking login status: {e!r}")
            return False

    def try_restore_session(self) -> bool:
        """Try to restore previous session using saved cookies."""
        if not self.session_manager.has_saved_session():
            logger.info("No saved session to restore")
            return False

        logger.info("Attempting to restore session from saved cookies")

        if self.session_manager.load_cookies(self.driver):
            if self.is_logged_in():
                logger.info("Successfully restored session")
                return True
            else:
                logger.warning("Session restored but login verification failed")

        return False

    def login(self, save_session: bool = True) -> bool:
        """Perform Twitter login with 2FA support."""
        logger.info("Starting Twitter login process")

        # First try to restore existing session
        if self.try_restore_session():
            return True

        # If restore failed, do fresh login
        return self._fresh_login(save_session)

    def _fresh_login(self, save_session: bool = True) -> bool:
        """Perform fresh login to Twitter."""
        missing_creds = self.config.validate()
        if missing_creds:
            logger.error(f"Missing credentials: {', '.join(missing_creds)}")
            return False

        try:
            logger.info("Navigating to X.com")
            self.debug_capture.log_action("Starting fresh login", f"Navigating to {self.config.front_page}")
            self.driver.get(self.config.front_page)
            time.sleep(5)
            self.debug_capture.capture_step("main_page", "Loaded X.com main page")

            # Look for and click sign in button if we're not logged in
            try:
                sign_in_btn = self.driver.find_element(By.XPATH, "//a[contains(@href, '/login') or contains(text(), 'Sign in')]")
                self.debug_capture.log_action("Found sign in button", "Clicking sign in")
                sign_in_btn.click()
                time.sleep(3)
                self.debug_capture.capture_step("clicked_signin", "Clicked sign in button")
            except NoSuchElementException:
                logger.info("No sign in button found, may already be on login page")
                self.debug_capture.capture_step("no_signin_btn", "No sign in button found")

            # Enter username
            if not self._enter_username():
                return False

            # Enter password
            if not self._enter_password():
                return False

            # Handle 2FA if required
            if not self._handle_2fa():
                return False

            # Verify login success
            if self._verify_login():
                if save_session:
                    self.session_manager.save_cookies(self.driver)
                logger.info("Login successful")
                return True
            else:
                logger.error("Login verification failed")
                return False

        except Exception as e:
            logger.error(f"Login failed with error: {e}")
            self._save_error_screenshot("login-error")
            return False

    def _enter_username(self) -> bool:
        """Enter username in login form."""
        try:
            logger.info("Entering username")
            self.debug_capture.log_action("Entering username", "Looking for username input field")

            xpath = "//*[text()='Phone, email, or username']"
            self.debug_capture.capture_element_info("username_search", xpath)

            username_input = self.wait.until(
                expected_conditions.presence_of_element_located((By.XPATH, xpath))
            )

            ActionChains(self.driver).move_to_element(username_input).click().send_keys(
                self.config.username
            ).perform()

            self._save_screenshot("username-input")
            self.debug_capture.capture_step("username_entered", "Username entered in form")
            time.sleep(1 + random.random())

            # Click Next
            self.debug_capture.log_action("Clicking Next", "After username entry")
            next_btn = self.driver.find_element(By.XPATH, "//*[text()='Next']")
            ActionChains(self.driver).move_to_element(next_btn).click().perform()
            self.debug_capture.capture_step("username_next_clicked", "Clicked Next after username")

            return True
        except Exception as e:
            logger.error(f"Failed to enter username: {e!r}")
            self.debug_capture.capture_error("username_entry_failed", e)
            return False

    def _enter_password(self) -> bool:
        """Enter password in login form."""
        try:
            logger.info("Entering password")
            self.debug_capture.log_action("Entering password", "Looking for password input field")
            time.sleep(3 + random.random())

            xpath = "//*[text()='Password']"
            self.debug_capture.capture_element_info("password_search", xpath)

            password_input = self.wait.until(
                expected_conditions.presence_of_element_located((By.XPATH, xpath))
            )

            ActionChains(self.driver).move_to_element(password_input).click().send_keys(
                self.config.password
            ).perform()

            self._save_screenshot("password-input")
            self.debug_capture.capture_step("password_entered", "Password entered in form")

            # Click Log in
            self.debug_capture.log_action("Clicking Log in", "After password entry")
            login_btn = self.driver.find_element(By.XPATH, "//*[text()='Log in']")
            ActionChains(self.driver).move_to_element(login_btn).click().perform()
            self.debug_capture.capture_step("login_clicked", "Clicked Log in button")

            time.sleep(5)
            return True
        except Exception as e:
            logger.error(f"Failed to enter password: {e!r}")
            self.debug_capture.capture_error("password_entry_failed", e)
            return False

    def _handle_2fa(self) -> bool:
        """Handle 2-factor authentication if required."""
        try:
            # Check if 2FA is required
            self.debug_capture.log_action("Checking for 2FA", "Looking for Enter code field")
            self.debug_capture.capture_step("2fa_check", "Checking if 2FA is required")

            code_input = self.driver.find_element(By.XPATH, "//*[text()='Enter code']")
            logger.info("2FA required")
            self.debug_capture.capture_step("2fa_required", "2FA code input field found")

            # Try backup code first if available
            if self.config.backup_code:
                logger.info("Using backup code for 2FA")
                self.debug_capture.log_action("Using backup code", "Entering 2FA backup code")
                ActionChains(self.driver).move_to_element(code_input).click().send_keys(
                    self.config.backup_code
                ).perform()
            else:
                # Interactive 2FA
                logger.info("Interactive 2FA required")
                self.debug_capture.log_action("Interactive 2FA", "Waiting for user input")
                auth_code = input("Please input 2-step auth code: ")
                ActionChains(self.driver).move_to_element(code_input).click().send_keys(
                    auth_code
                ).perform()

            self.debug_capture.capture_step("2fa_code_entered", "2FA code entered")

            # Click Next
            self.debug_capture.log_action("Clicking Next", "After 2FA code entry")
            next_btn = self.driver.find_element(By.XPATH, "//*[text()='Next']")
            ActionChains(self.driver).move_to_element(next_btn).click().perform()

            self._save_screenshot("after-2fa")
            self.debug_capture.capture_step("2fa_next_clicked", "Clicked Next after 2FA")
            time.sleep(5)
            return True

        except NoSuchElementException:
            logger.info("No 2FA required")
            return True
        except Exception as e:
            logger.error(f"2FA handling failed: {e!r}")
            return False

    def _verify_login(self) -> bool:
        """Verify that login was successful by checking current URL."""
        self.debug_capture.log_action("Verifying login", "Checking current URL after login attempt")
        
        for attempt in range(self.config.max_error_count):
            try:
                current_url = self.driver.current_url
                self.debug_capture.capture_step(f"verify_attempt_{attempt + 1}", f"Checking URL: {current_url}")
                
                # If we're on x.com/home or similar logged-in pages, login was successful
                success_url_patterns = [
                    "x.com/home",
                    "twitter.com/home", 
                    f"x.com/{self.config.username}",
                    f"twitter.com/{self.config.username}",
                ]
                
                if any(pattern in current_url for pattern in success_url_patterns):
                    logger.info(f"Login verified - on success URL: {current_url}")
                    self.debug_capture.log_action("Login verified", f"Success URL detected: {current_url}")
                    
                    # Handle any post-login prompts
                    try:
                        no_ads = self.driver.find_element(By.XPATH, "//*[text()='Keep less relevant ads']")
                        ActionChains(self.driver).move_to_element(no_ads).click().perform()
                        self.debug_capture.log_action("Handled post-login prompt", "Clicked ads preference")
                        time.sleep(2)
                    except NoSuchElementException:
                        pass
                    
                    return True
                
                # If we're still on login/flow pages, login failed
                failure_url_patterns = [
                    "x.com/i/flow/login",
                    "twitter.com/i/flow/login",
                    "x.com/login",
                    "twitter.com/login",
                ]
                
                if any(pattern in current_url for pattern in failure_url_patterns):
                    logger.warning(f"Login failed - still on login page: {current_url}")
                    self.debug_capture.capture_step("login_failed", f"Still on login URL: {current_url}")
                    return False
                
                # If URL is unclear, wait and retry
                logger.info(f"URL unclear, waiting and retrying... Current: {current_url}")
                time.sleep(self.config.login_wait)

            except Exception as e:
                logger.error(f"Login verification error: {e}")
                self.debug_capture.capture_error("login_verification_error", e)

        self._save_error_screenshot("login-verification-failed")
        self.debug_capture.capture_step("verification_failed", "All login verification attempts failed")
        return False

    def _save_screenshot(self, name: str) -> None:
        """Save screenshot for debugging."""
        try:
            screenshot_path = self.config.screenshot_path / f"{name}.png"
            self.driver.save_screenshot(str(screenshot_path))
            logger.debug(f"Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Failed to save screenshot {name}: {e}")

    def _save_error_screenshot(self, name: str) -> None:
        """Save error screenshot."""
        try:
            screenshot_path = self.config.screenshot_path / f"error-{name}.png"
            self.driver.save_screenshot(str(screenshot_path))
            logger.error(f"Error screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.warning(f"Failed to save error screenshot {name}: {e}")

    def ensure_likes_page(self) -> bool:
        """Ensure we're on the user's likes page."""
        try:
            likes_url = f"https://x.com/{self.config.username}/likes"
            current_url = self.driver.current_url

            if likes_url not in current_url:
                logger.info(f"Navigating to likes page: {likes_url}")
                self.debug_capture.log_action("Navigating to likes", f"From {current_url} to {likes_url}")
                self.driver.get(likes_url)
                time.sleep(5)
                self.debug_capture.capture_step("likes_page_loaded", f"Loaded {likes_url}")

            return True
        except Exception as e:
            logger.error(f"Failed to navigate to likes page: {e}")
            self.debug_capture.capture_error("likes_navigation_failed", e)
            return False

    def logout(self) -> bool:
        """Logout and clear session."""
        try:
            # Clear browser session
            self.driver.delete_all_cookies()

            # Clear saved session
            self.session_manager.clear_session()

            logger.info("Logged out successfully")
            return True
        except Exception as e:
            logger.error(f"Logout failed: {e}")
            return False
