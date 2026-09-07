"""
One-time authorization against the Spotify API.

Run this interactively (it needs terminal access) BEFORE the first
start of the spotify-collector systemd service, since that service
runs in the background without a terminal and can't show the login
link itself.

The script prints a URL to open in your browser, log in with your
Spotify account, then paste back here the full URL you get
redirected to (even if the page doesn't load, just copy the address
from the browser bar). The access/refresh token is saved to
data/.cache and refreshes itself automatically from then on.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from spotipy.oauth2 import SpotifyOAuth  # noqa: E402

from config import (  # noqa: E402
    CACHE_PATH,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE,
    require_spotify_credentials,
)

require_spotify_credentials()

auth_manager = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SPOTIFY_SCOPE,
    open_browser=False,
    cache_path=CACHE_PATH,
)

token_info = auth_manager.cache_handler.get_cached_token()
if token_info and not auth_manager.is_token_expired(token_info):
    print("Already authorized, the token is valid. Nothing to do.")
    sys.exit(0)

print("Open this URL in your browser and log in with your Spotify account:\n")
print(auth_manager.get_authorize_url())
print("\nAfter logging in, the browser will redirect you to the redirect URI "
      "from .env (the page doesn't need to actually load, that's fine).")
print("Copy the ENTIRE resulting URL from the address bar and paste it here:\n")

redirect_response = input("Redirected URL: ").strip()
code = auth_manager.parse_response_code(redirect_response)
auth_manager.get_access_token(code, as_dict=False)

print("\nDone. The token is saved in data/.cache. You can now start/restart "
      "the spotify-collector service.")
