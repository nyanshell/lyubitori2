"""Command-line interface for Twitter image scraper."""

import logging
import sys
from pathlib import Path

import click

from .auth import TwitterAuth
from .config import Config
from .driver import DriverManager
from .scraper import TwitterImageScraper
from .session import SessionManager


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Configure logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(logs_dir / "twitter_scraper.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Set selenium logging to WARNING to reduce noise
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--debug", is_flag=True, help="Enable debug mode with screenshots and HTML capture")
@click.pass_context
def cli(ctx, verbose, debug):
    """Twitter image scraper CLI tool."""
    setup_logging(verbose)

    # Store config in context
    config = Config()
    if debug:
        config.enable_debug()

    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose
    ctx.obj["debug"] = debug


@cli.command()
@click.option(
    "--save-session/--no-save-session",
    default=True,
    help="Save session cookies for reuse",
)
@click.pass_context
def login(ctx, save_session):
    """Login to Twitter and optionally save session."""
    config = ctx.obj["config"]

    # Check for required credentials
    missing = config.validate()
    if missing:
        click.echo(
            f"❌ Missing required environment variables: {', '.join(missing)}", err=True
        )
        click.echo("Please set these in your .env file or environment", err=True)
        sys.exit(1)

    driver_manager = DriverManager(config)
    session_manager = SessionManager(config.session_path)

    try:
        driver = driver_manager.create_driver()
        auth = TwitterAuth(driver, config, session_manager)

        click.echo("🔐 Attempting Twitter login...")

        if auth.login(save_session=save_session):
            click.echo("✅ Login successful!")
            if save_session:
                click.echo("💾 Session saved for future use")
        else:
            click.echo("❌ Login failed", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error during login: {e}", err=True)
        sys.exit(1)
    finally:
        driver_manager.quit_driver()


@cli.command()
@click.option(
    "--max-scroll", "-s", default=100, help="Maximum number of scroll iterations"
)
@click.option(
    "--no-login", is_flag=True, help="Skip login attempt (use existing session)"
)
@click.pass_context
def download(ctx, max_scroll, no_login):
    """Download images from your Twitter likes."""
    config = ctx.obj["config"]

    driver_manager = DriverManager(config)
    session_manager = SessionManager(config.session_path)

    try:
        driver = driver_manager.create_driver()
        auth = TwitterAuth(driver, config, session_manager)
        scraper = TwitterImageScraper(driver, config)

        # Handle authentication
        if not no_login:
            click.echo("🔐 Checking authentication...")
            if not auth.login():
                click.echo("❌ Authentication failed", err=True)
                sys.exit(1)
            click.echo("✅ Authentication successful")

            # Ensure we're on the likes page
            click.echo("🔗 Navigating to likes page...")
            if not auth.ensure_likes_page():
                click.echo("❌ Failed to navigate to likes page", err=True)
                sys.exit(1)

        # Start scraping
        click.echo(f"🚀 Starting image scrape (max {max_scroll} scrolls)")
        click.echo(f"📁 Images will be saved to: {config.save_path}")

        if config.debug_mode:
            click.echo(f"🐛 Debug mode enabled - captures will be saved to: {config.debug_path}")

        click.echo(f"🌐 Target URL: {config.likes_url}")

        total_images = scraper.scroll_and_download(max_scroll=max_scroll)

        click.echo(f"✅ Scraping completed! Processed {total_images} images")

    except KeyboardInterrupt:
        click.echo("\n⏹️  Scraping interrupted by user")
    except Exception as e:
        click.echo(f"❌ Scraping error: {e}", err=True)
        sys.exit(1)
    finally:
        driver_manager.quit_driver()


@cli.command()
@click.pass_context
def status(ctx):
    """Check authentication status and session info."""
    config = ctx.obj["config"]
    session_manager = SessionManager(config.session_path)

    click.echo("📊 Twitter Scraper Status")
    click.echo("=" * 30)

    # Check environment variables
    missing = config.validate()
    if missing:
        click.echo(f"❌ Missing credentials: {', '.join(missing)}")
    else:
        click.echo("✅ Credentials configured")

    # Check saved session
    if session_manager.has_saved_session():
        cookies_file = session_manager.cookies_file
        mod_time = cookies_file.stat().st_mtime
        import datetime

        mod_date = datetime.datetime.fromtimestamp(mod_time)
        click.echo(f"💾 Saved session: {cookies_file} (modified: {mod_date})")
    else:
        click.echo("❌ No saved session found")

    # Check directories
    click.echo(f"📁 Download directory: {config.save_path}")
    click.echo(f"📁 Session directory: {config.session_path}")
    click.echo(f"📁 Screenshot directory: {config.screenshot_path}")

    # Debug mode status
    if config.debug_mode:
        click.echo("🐛 Debug mode: ENABLED")
        click.echo(f"📁 Debug directory: {config.debug_path}")
    else:
        click.echo("🐛 Debug mode: DISABLED")

    # Check if logged in (requires starting browser)
    click.echo("\n🔍 Checking live authentication status...")
    driver_manager = DriverManager(config)
    try:
        driver = driver_manager.create_driver()
        auth = TwitterAuth(driver, config, session_manager)

        if auth.is_logged_in():
            click.echo("✅ Currently logged in to Twitter")
        else:
            click.echo("❌ Not logged in to Twitter")

    except Exception as e:
        click.echo(f"⚠️  Could not check login status: {e}")
    finally:
        driver_manager.quit_driver()


@cli.command()
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def logout(ctx, confirm):
    """Logout and clear saved session."""
    config = ctx.obj["config"]
    session_manager = SessionManager(config.session_path)

    if not confirm and not click.confirm(
        "Are you sure you want to logout and clear saved session?"
    ):
        click.echo("Logout cancelled")
        return

    driver_manager = DriverManager(config)

    try:
        driver = driver_manager.create_driver()
        auth = TwitterAuth(driver, config, session_manager)

        if auth.logout():
            click.echo("✅ Logged out successfully")
        else:
            click.echo("⚠️  Logout may not have completed fully")

    except Exception as e:
        click.echo(f"⚠️  Error during logout: {e}")
        # Still try to clear local session
        session_manager.clear_session()
        click.echo("🧹 Local session data cleared")
    finally:
        driver_manager.quit_driver()



@cli.command()
@click.option("--host", "-h", default="0.0.0.0", help="Host to bind API server")
@click.option("--port", "-p", default=5000, help="Port to bind API server")
@click.option("--debug", is_flag=True, help="Run in debug mode")
@click.pass_context
def serve(ctx, host, port, debug):
    """Start the Lyubitori API server."""

    click.echo(f"🚀 Starting Lyubitori API server on {host}:{port}")
    if debug:
        click.echo("⚠️  Debug mode enabled")

    try:
        # Import here to avoid circular imports
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent))

        from app import app

        app.run(host=host, port=port, debug=debug)
    except KeyboardInterrupt:
        click.echo("\n⏹️  API server stopped")
    except Exception as e:
        click.echo(f"❌ Failed to start API server: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
