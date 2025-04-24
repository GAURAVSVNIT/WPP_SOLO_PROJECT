CLIENT_ID = "62f09e6100ee44568d79156869b6a757"
CLIENT_SECRET = "c3086b4a14e04c3c9a080ebbb0973d68"
REDIRECT_URI = "http://127.0.0.1:8000/spotify/redirect"

# Comprehensive list of required Spotify scopes
SCOPE = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "app-remote-control",
    "streaming",
    "playlist-read-private",
    "user-read-playback-position",
    "user-top-read",
    "user-read-recently-played"
])
