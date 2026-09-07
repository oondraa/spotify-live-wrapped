import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = str(DATA_DIR / "spotify_history.db")
CACHE_PATH = str(DATA_DIR / ".cache")

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.environ.get("SPOTIFY_REDIRECT_URI")
SPOTIFY_SCOPE = "user-read-recently-played user-follow-read"

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
FLASK_SECRET_KEY = os.environ.get("FLASK_SECRET_KEY")

WEB_HOST = os.environ.get("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.environ.get("WEB_PORT", "5000"))

COLLECT_INTERVAL_SECONDS = int(os.environ.get("COLLECT_INTERVAL_SECONDS", "600"))


def require_spotify_credentials():
    missing = [
        name
        for name, value in (
            ("SPOTIFY_CLIENT_ID", SPOTIFY_CLIENT_ID),
            ("SPOTIFY_CLIENT_SECRET", SPOTIFY_CLIENT_SECRET),
            ("SPOTIFY_REDIRECT_URI", SPOTIFY_REDIRECT_URI),
        )
        if not value
    ]
    if missing:
        print(
            "Missing required variables in .env: " + ", ".join(missing) + "\n"
            "Copy .env.example to .env and fill in the values from the Spotify Developer "
            "Dashboard, or run deploy/install.sh.",
            file=sys.stderr,
        )
        sys.exit(1)
