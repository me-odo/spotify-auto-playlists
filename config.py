import os
from dotenv import load_dotenv

load_dotenv()

# Base & cache directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
DIFF_DIR = os.path.join(CACHE_DIR, "diffs")

# Cache files
TRACKS_CACHE_FILE = os.path.join(CACHE_DIR, "tracks.json")
FEATURES_CACHE_FILE = os.path.join(CACHE_DIR, "audio_features.json")
CLASSIFICATION_CACHE_FILE = os.path.join(CACHE_DIR, "track_classification_cache.json")

# Spotify credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv(
    "SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"
)

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Spotify API constants
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

SCOPES = [
    "user-library-read",
    "playlist-read-private",
    "playlist-modify-private",
    "playlist-modify-public",
]

# Playlist name prefixes
PLAYLIST_PREFIX_MOOD = "Auto – Mood – "
PLAYLIST_PREFIX_GENRE = "Auto – Genre – "
PLAYLIST_PREFIX_YEAR = "Auto – Year – "
