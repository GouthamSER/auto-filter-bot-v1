import re
from os import environ

id_pattern = re.compile(r'^-?\d+$')


def parse_ids(env_key, default=""):
    raw = environ.get(env_key, default).split()
    return [int(x) if id_pattern.match(x) else x for x in raw if x]


# ── Bot Credentials ─────────────────────────────────────────────────────────
SESSION       = environ.get("SESSION", "MediaSearchBot")
API_ID        = int(environ["API_ID"])
API_HASH      = environ["API_HASH"]
BOT_TOKEN     = environ["BOT_TOKEN"]

# ── Database ─────────────────────────────────────────────────────────────────
DATABASE_URI     = environ["DATABASE_URI"]
DATABASE_NAME    = environ.get("DATABASE_NAME", "")
COLLECTION_NAME  = environ.get("COLLECTION_NAME", "v1files")

# ── Channels / Admins ────────────────────────────────────────────────────────
# Space-separated list of channel IDs/usernames to auto-index
CHANNELS     = parse_ids("CHANNELS")
ADMINS       = parse_ids("ADMINS")
AUTH_USERS   = parse_ids("AUTH_USERS") + ADMINS

URL = environ.get("URL", "") #keepalive url 

# Optional: channel users must join before using bot
AUTH_CHANNEL = environ.get("AUTH_CHANNEL")
AUTH_CHANNEL = int(AUTH_CHANNEL) if AUTH_CHANNEL and id_pattern.match(AUTH_CHANNEL) else AUTH_CHANNEL

# Optional: channel for bot logs
LOG_CHANNEL_RAW = environ.get("LOG_CHANNEL", "")
LOG_CHANNEL = int(LOG_CHANNEL_RAW) if LOG_CHANNEL_RAW and id_pattern.match(LOG_CHANNEL_RAW) else None

# ── Search Settings ───────────────────────────────────────────────────────────
MAX_RESULTS         = int(environ.get("MAX_RESULTS", 10))   # results per page
CACHE_TIME          = int(environ.get("CACHE_TIME", 300))   # inline cache (seconds)
USE_CAPTION_FILTER  = environ.get("USE_CAPTION_FILTER", "false").lower() == "true"

# ── Messages ──────────────────────────────────────────────────────────────────
START_MSG = environ.get(
    "START_MSG",
    "👋 <b>Hi {mention}!</b>\n\n"
    "🔍 <b>Send me any movie or file name</b> and I'll search the database for you!\n\n"
    "📌 <b>Tips:</b>\n"
    "• Use <code>name | video</code> to filter by type\n"
    "• Use inline: <code>@{username} movie name</code>"
)

FORCE_SUB_MSG = environ.get(
    "FORCE_SUB_MSG",
    "⚠️ <b>You must join our channel first!</b>\n\n"
    "👉 Join and then try again."
)
