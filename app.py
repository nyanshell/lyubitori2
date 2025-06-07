"""RESTful API for Lyubitori."""

import logging
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

from twitter_scraper.config import Config
from twitter_scraper.driver import DriverManager
from twitter_scraper.scraper import TwitterImageScraper
from twitter_scraper.session import SessionManager

type TaskDict = dict[str, TaskInfo]
type ThreadDict = dict[str, threading.Thread]

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """Information about a download task."""

    task_id: str
    status: TaskStatus
    url: str | None
    max_scroll: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    progress: dict[str, Any] = None
    results: dict[str, Any] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON response."""
        data = asdict(self)
        data["status"] = self.status.value
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["started_at"] = self.started_at.isoformat() if self.started_at else None
        data["completed_at"] = (
            self.completed_at.isoformat() if self.completed_at else None
        )
        return data


# Global state
config = Config()
tasks: TaskDict = {}
active_tasks: ThreadDict = {}
task_lock = threading.Lock()

# Shared driver components
driver_manager: DriverManager | None = None
session_manager = SessionManager(config.session_path)
scraper: TwitterImageScraper | None = None
driver_lock = threading.Lock()

# Create Flask app
app = Flask(__name__)
CORS(app)


def ensure_driver() -> bool:
    """Ensure driver and related components are initialized."""
    global driver_manager, scraper

    try:
        if not driver_manager:
            driver_manager = DriverManager(config)

        driver = driver_manager.get_driver()

        if not scraper:
            scraper = TwitterImageScraper(driver, config)

        return True
    except Exception as e:
        logger.error(f"Failed to ensure driver: {e}")
        return False


def check_authentication() -> bool:
    """Check if currently authenticated (assumes user is logged in)."""
    try:
        if not ensure_driver():
            return False
        return session_manager.has_saved_session()
    except Exception as e:
        logger.error(f"Authentication check error: {e}")
        return False


def cleanup_driver():
    """Clean up driver resources."""
    global driver_manager, scraper

    if driver_manager:
        driver_manager.quit_driver()
        driver_manager = None
    scraper = None


def run_download_task(task_id: str, debug_mode: bool = False):
    """Run a download task in background."""
    global tasks

    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return

    try:
        # Update task status
        with task_lock:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now()

        logger.info(f"Starting download task {task_id}: {task.url} (debug: {debug_mode})")

        # Enable debug mode if requested
        if debug_mode:
            config.enable_debug()

        # Ensure driver is ready
        with driver_lock:
            if not ensure_driver():
                raise Exception("Failed to initialize driver")

            # Navigate to likes page (assuming user is logged in)
            driver = driver_manager.get_driver()
            driver.get(config.likes_url)

            # Start downloading with progress tracking
            total_images = 0
            loop = 0
            previous_urls = set()

            while loop < task.max_scroll:
                # Check if task was cancelled
                with task_lock:
                    if task.status == TaskStatus.CANCELLED:
                        logger.info(f"Task {task_id} was cancelled")
                        return

                try:
                    last_img, viewed_urls = scraper.download_visible_images()

                    # Update progress
                    new_images = len(viewed_urls - previous_urls)
                    total_images += new_images
                    previous_urls = viewed_urls

                    with task_lock:
                        task.progress = {
                            "images_processed": total_images,
                            "scroll_iterations": loop + 1,
                            "current_page_images": len(viewed_urls),
                        }

                    # Check if no new content
                    if len(viewed_urls.union(previous_urls)) == len(previous_urls):
                        logger.info(f"No new content found for task {task_id}")
                        break

                    # Scroll down
                    if last_img:
                        from selenium.webdriver import ActionChains

                        ActionChains(scraper.driver).scroll_to_element(
                            last_img
                        ).perform()
                        time.sleep(config.scroll_delay)

                except Exception as e:
                    logger.warning(
                        f"Error in scroll iteration {loop} for task {task_id}: {e}"
                    )

                loop += 1

        # Task completed successfully
        with task_lock:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.results = {
                "total_images_processed": total_images,
                "scroll_iterations_completed": loop,
                "download_path": str(config.save_path),
                "debug_enabled": debug_mode,
                "debug_path": str(config.debug_path) if debug_mode else None,
            }

        logger.info(
            f"Task {task_id} completed successfully: {total_images} images processed"
        )

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        with task_lock:
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.now()
            task.error_message = str(e)

    finally:
        # Clean up active task reference
        with task_lock:
            active_tasks.pop(task_id, None)


# API Routes
@app.route("/status", methods=["GET"])
def status():
    """Get API and authentication status."""
    try:
        with driver_lock:
            is_authenticated = check_authentication()

        return jsonify(
            {
                "status": "ok",
                "authenticated": is_authenticated,
                "session_saved": session_manager.has_saved_session(),
                "active_tasks": len(active_tasks),
                "total_tasks": len(tasks),
                "config": {
                    "save_path": str(config.save_path),
                    "likes_url": config.likes_url,
                    "debug_mode": config.debug_mode,
                    "debug_path": str(config.debug_path) if config.debug_mode else None,
                },
            }
        )
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/download", methods=["POST"])
def download():
    """Start a new download task."""
    try:
        data = request.get_json() or {}
        max_scroll = data.get("max_scroll", 100)
        debug_mode = data.get("debug", False)

        task_id = str(uuid.uuid4())
        task = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            url=config.likes_url,
            max_scroll=max_scroll,
            created_at=datetime.now(),
            progress={"images_processed": 0, "scroll_iterations": 0},
            results={},
        )

        with task_lock:
            tasks[task_id] = task

        # Start background task
        thread = threading.Thread(
            target=run_download_task, args=(task_id, debug_mode), daemon=True
        )
        thread.start()

        with task_lock:
            active_tasks[task_id] = thread

        return jsonify(
            {
                "status": "success",
                "task_id": task_id,
                "message": "Download task started",
                "debug_enabled": debug_mode,
            }
        )

    except Exception as e:
        logger.error(f"Download start error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/refresh", methods=["POST"])
def refresh():
    """Refresh/restart the current page and download new content."""
    try:
        data = request.get_json() or {}
        max_scroll = data.get("max_scroll", 50)
        debug_mode = data.get("debug", False)

        # Create a refresh task (similar to download but different semantics)
        task_id = str(uuid.uuid4())
        task = TaskInfo(
            task_id=task_id,
            status=TaskStatus.PENDING,
            url=config.likes_url,
            max_scroll=max_scroll,
            created_at=datetime.now(),
            progress={"images_processed": 0, "scroll_iterations": 0},
            results={},
        )

        with task_lock:
            tasks[task_id] = task

        # Start background task
        thread = threading.Thread(
            target=run_download_task, args=(task_id, debug_mode), daemon=True
        )
        thread.start()

        with task_lock:
            active_tasks[task_id] = thread

        return jsonify(
            {
                "status": "success",
                "task_id": task_id,
                "message": "Refresh task started",
                "debug_enabled": debug_mode,
            }
        )

    except Exception as e:
        logger.error(f"Refresh error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/tasks", methods=["GET"])
def get_tasks():
    """Get all tasks."""
    with task_lock:
        tasks_data = [task.to_dict() for task in tasks.values()]
    return jsonify({"tasks": tasks_data})


@app.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """Get specific task information."""
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({"status": "error", "message": "Task not found"}), 404
        return jsonify(task.to_dict())


@app.route("/tasks/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    """Cancel a running task."""
    with task_lock:
        task = tasks.get(task_id)
        if not task:
            return jsonify({"status": "error", "message": "Task not found"}), 404

        if task.status in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]:
            return jsonify({"status": "error", "message": "Task already finished"}), 400

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now()

    return jsonify({"status": "success", "message": "Task cancelled"})



@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})


@app.route("/", methods=["GET"])
def index():
    """Basic info page."""
    return jsonify(
        {
            "service": "Lyubitori API",
            "version": "1.0.0",
            "endpoints": {
                "GET /status": "Get API status and authentication state",
                "POST /download": "Start download task",
                "POST /refresh": "Refresh and download new content",
                "GET /tasks": "Get all tasks",
                "GET /tasks/<id>": "Get specific task",
                "POST /tasks/<id>/cancel": "Cancel task",
                "GET /health": "Health check",
            },
        }
    )


if __name__ == "__main__":
    import atexit

    atexit.register(cleanup_driver)

    import os

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 5000))
    debug = os.getenv("API_DEBUG", "false").lower() == "true"

    logger.info(f"Starting Lyubitori API on {host}:{port}")
    app.run(host=host, port=port, debug=debug)
