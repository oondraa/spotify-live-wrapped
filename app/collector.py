import sqlite3
import time
from datetime import datetime

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from config import (
    CACHE_PATH,
    COLLECT_INTERVAL_SECONDS,
    DB_PATH,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
    SPOTIFY_SCOPE,
    require_spotify_credentials,
)

require_spotify_credentials()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SPOTIFY_SCOPE,
    open_browser=False,
    cache_path=CACHE_PATH,
))


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history
                 (played_at TEXT PRIMARY KEY, track_id TEXT, track_name TEXT,
                  artist_id TEXT, artist_name TEXT, album_name TEXT,
                  image_url TEXT, duration_ms INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS following_artists
                 (artist_id TEXT PRIMARY KEY, name TEXT, image_url TEXT, genres TEXT)''')
    conn.commit()
    conn.close()


def save_to_db(recent_tracks):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    count = 0
    for item in recent_tracks['items']:
        t = item['track']
        played_at = item['played_at']
        artist_id = t['artists'][0]['id']
        try:
            c.execute('INSERT OR IGNORE INTO history VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                      (played_at, t['id'], t['name'], artist_id, t['artists'][0]['name'],
                       t['album']['name'], t['album']['images'][0]['url'], t['duration_ms']))
            if c.rowcount > 0:
                count += 1
        except Exception as e:
            print(f"Error: {e}")
    conn.commit()
    conn.close()
    if count > 0:
        print(f"{datetime.now()}: Saved {count} new tracks.")


def update_following():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        results = sp.current_user_followed_artists(limit=50)
        artists = results['artists']['items']
        c.execute('DELETE FROM following_artists')
        for a in artists:
            img = a['images'][0]['url'] if a['images'] else ""
            genres = ", ".join(a['genres'])
            c.execute('INSERT INTO following_artists VALUES (?, ?, ?, ?)',
                      (a['id'], a['name'], img, genres))
        conn.commit()
        conn.close()
        print(f"{datetime.now()}: Updated {len(artists)} followed artists.")
    except Exception as e:
        print(f"Error updating followed artists: {e}")


def main():
    init_db()
    print("Collector started...")
    while True:
        try:
            recent_tracks = sp.current_user_recently_played(limit=50)
            save_to_db(recent_tracks)
            update_following()
        except Exception as e:
            print(f"Error: {e}")
        time.sleep(COLLECT_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
