import re
from os import environ

id_pattern = re.compile(r'^-?\d+$')


def parse_ids(env_key, default=""):
    raw = environ.get(env_key, default).split()
    return [int(x) if id_pattern.match(x) else x for x in raw if x]


# ── Bot Credentials ──────────────────────────────────────────────────────────
SESSION       = environ.get("SESSION", "MediaSearchBot")
API_ID        = int(environ["API_ID"])
API_HASH      = environ["API_HASH"]
BOT_TOKEN     = environ["BOT_TOKEN"]

# ── Primary Database (required) ───────────────────────────────────────────────
DATABASE_URI     = environ["DATABASE_URI"]
DATABASE_NAME    = environ.get("DATABASE_NAME", "MediaSearchDB")
COLLECTION_NAME  = environ.get("COLLECTION_NAME", "tgfls")

# ── Secondary Database (optional) ─────────────────────────────────────────────
# If set: new files & users are saved here; search falls back to DB1 if DB2
# has no results. If not set: only DB1 is used.
DATABASE_URI_2    = environ.get("DATABASE_URI_2", "")
DATABASE_NAME_2   = environ.get("DATABASE_NAME_2", DATABASE_NAME)
COLLECTION_NAME_2 = environ.get("COLLECTION_NAME_2", COLLECTION_NAME)

# ── Channels / Admins ────────────────────────────────────────────────────────
CHANNELS   = parse_ids("CHANNELS")
ADMINS     = parse_ids("ADMINS")
AUTH_USERS = parse_ids("AUTH_USERS") + ADMINS

URL = environ.get("URL", "")  # keep-alive url

# Optional: channel users must join before using bot
AUTH_CHANNEL = environ.get("AUTH_CHANNEL")
AUTH_CHANNEL = int(AUTH_CHANNEL) if AUTH_CHANNEL and id_pattern.match(AUTH_CHANNEL) else AUTH_CHANNEL

# Optional: channel for bot logs
LOG_CHANNEL_RAW = environ.get("LOG_CHANNEL", "")
LOG_CHANNEL = int(LOG_CHANNEL_RAW) if LOG_CHANNEL_RAW and id_pattern.match(LOG_CHANNEL_RAW) else None

# ── Search Settings ───────────────────────────────────────────────────────────
MAX_RESULTS        = int(environ.get("MAX_RESULTS", 10))
CACHE_TIME         = int(environ.get("CACHE_TIME", 300))
USE_CAPTION_FILTER = environ.get("USE_CAPTION_FILTER", "false").lower() == "true"

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
