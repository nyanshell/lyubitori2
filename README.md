# Lyubitori

Download images from Your X(Twitter) likes using Selenium & Chrome WebDriver.

## Requirements

- **Python 3.13+**

## Installation

```bash
pip install -r requirements.txt
pip install -r dev-requirements.txt  # For development
```

## Configuration

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Edit `.env` with your Twitter credentials:
```env
USERNAME=your_twitter_username
PASSWORD=your_twitter_password
BACKUP_CODE=your_2fa_backup_code(optional, if you want use login with backup code)
```

## Usage

### Quick Start

#### Run remote Chrome

```bash
chromedriver --allowed-ips=LIST_OF_IPS
```

#### Basic Commands

```bash
# Check configuration and status
python main.py status

# Login to Twitter (saves session)
python main.py login

# Download images from your likes
python main.py download --max-scroll 100

# Start API server
python main.py serve --port 5000
```

If you're running remote chrome, even no saved session, you could still continue download without login next time(if the chrome profile is not cleared).

### Available Commands

```bash
# Authentication
python main.py login              # Login and save session
python main.py logout             # Logout and clear session
python main.py status             # Check authentication status

# Downloading
python main.py download                   # Download from your likes
python main.py download --max-scroll 200 # Limit scroll iterations

# API Server
python main.py serve              # Start API server on localhost:5000
python main.py serve --host 0.0.0.0 --port 8080  # Custom host/port


# Enable verbose logging for any command
python main.py -v <command>

# Enable debug mode (captures screenshots and HTML for each step)
python main.py --debug <command>
```

### RESTful API

Start the API server:
```bash
python main.py serve --port 5000
```

Or run directly:
```bash
python app.py
```

#### API Endpoints

- `GET /api/status` - Get authentication and system status
- `POST /api/login` - Login to Twitter and save session
- `POST /api/logout` - Logout and clear session
- `POST /api/download` - Start download task
- `POST /api/refresh` - Refresh page and download new content
- `GET /api/tasks` - Get all tasks
- `GET /api/tasks/<id>` - Get specific task status
- `POST /api/tasks/<id>/cancel` - Cancel running task
- `GET /api/health` - Health check

#### API Usage Examples

```bash
# Check status
curl http://localhost:5000/api/status

# Start download task
curl -X POST http://localhost:5000/api/download \
  -H "Content-Type: application/json" \
  -d '{"max_scroll": 100}'

# Start download task with debug mode
curl -X POST http://localhost:5000/api/download \
  -H "Content-Type: application/json" \
  -d '{"max_scroll": 100, "debug": true}'

# Check task progress
curl http://localhost:5000/api/tasks/<task-id>

# Refresh and download new content
curl -X POST http://localhost:5000/api/refresh \
  -H "Content-Type: application/json" \
  -d '{"max_scroll": 50}'
```

### Session Management

The tool automatically saves your authentication session to avoid frequent logins:

- Sessions are saved in `session/cookies.json`
- Browser profile data in `session/chrome_profile/`
- Sessions restore automatically on subsequent runs
- Use `python main.py logout` to clear saved sessions

## Directory Structure

```
lyubitori2/
├── twitter_scraper/          # Main package
│   ├── auth.py              # Authentication handling
│   ├── cli.py               # Click CLI interface
│   ├── config.py            # Configuration management
│   ├── driver.py            # WebDriver management
│   ├── scraper.py           # Image scraping logic
│   └── session.py           # Session persistence
├── main.py                  # CLI entry point
├── run.py                   # Legacy script (preserved)
├── downloaded/              # Scraped images (auto-created)
├── session/                 # Session data (auto-created)
├── screenshots/             # Debug screenshots (auto-created)
├── debug/                   # Debug captures (auto-created when --debug used)
│   ├── screenshots/         # Step-by-step screenshots
│   └── html/                # HTML source captures
└── logs/                    # Application logs (auto-created)
```

## Legacy Usage (preserved)

The original interactive mode is still available:

```bash
dotenv run ipython -i run.py
```

```python
In [1]: twitter_login()
In [2]: driver.get("https://x.com/<username>/likes") 
In [3]: scroll_download(max_scroll=500)
```

## Development

### Code Quality

The project uses ruff for linting and formatting:

```bash
# Install development dependencies
pip install -r dev-requirements.txt

# Run linter
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code
ruff format .
```

## Debug Mode

The `--debug` flag enables comprehensive debugging capabilities:

```bash
# Enable debug mode for any command
python main.py --debug download --max-scroll 50
python main.py --debug login
```

**Debug Output Location:**
- `debug/screenshots/` - Step-by-step screenshots with timestamps
- `debug/html/` - HTML source captures and element information
- `debug/debug_summary.txt` - Summary of the debug session

**API Debug Mode:**
```bash
# Start download with debug enabled via API
curl -X POST http://localhost:5000/api/download \
  -H "Content-Type: application/json" \
  -d '{"debug": true}'
```
