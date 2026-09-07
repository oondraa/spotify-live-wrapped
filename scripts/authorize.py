"""
Jednorázová autorizace aplikace vůči Spotify API.

Spusť interaktivně (má přístup k terminálu) PŘED prvním startem
systemd služby spotify-collector, protože ta běží na pozadí bez
terminálu a nemůže sama zobrazit přihlašovací odkaz.

Skript vypíše URL, kterou otevřeš v prohlížeči, přihlásíš se ke
Spotify účtu, a poté sem vložíš celou URL, na kterou tě to přesměruje
(i když stránka nenačte, stačí zkopírovat adresu z prohlížeče).
Access/refresh token se uloží do data/.cache a od té chvíle se
obnovuje automaticky.
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
    print("Aplikace už je autorizovaná, token je platný. Nic není potřeba dělat.")
    sys.exit(0)

print("Otevři tuto URL v prohlížeči a přihlas se ke svému Spotify účtu:\n")
print(auth_manager.get_authorize_url())
print("\nPo přihlášení tě prohlížeč přesměruje na redirect URI z .env "
      "(stránka se nemusí načíst, to je v pořádku).")
print("Zkopíruj CELOU výslednou URL z adresního řádku a vlož ji sem:\n")

redirect_response = input("Vložená URL: ").strip()
code = auth_manager.parse_response_code(redirect_response)
auth_manager.get_access_token(code, as_dict=False)

print("\nHotovo. Token je uložený v data/.cache. Teď můžeš spustit/restartovat "
      "službu spotify-collector.")
