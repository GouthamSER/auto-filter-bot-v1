import logging
import asyncio
import os
from aiohttp import ClientSession, ClientTimeout
# Ensure URL is imported from config or os.environ
from aiohttp import web
from pyrogram import Client
from pyrogram.enums import ParseMode

from config import (
    API_ID, API_HASH, BOT_TOKEN, SESSION, LOG_CHANNEL,
    AUTH_CHANNEL, CHANNELS, URL
)
from database.db import Media

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── Web server port (Render/Koyeb inject PORT env var) ────────────────────────
PORT = int(os.environ.get("PORT", 8080))


# ─────────────────────────────────────────────────────────────────────────────
#  Tiny aiohttp app – keeps the dyno/container alive
# ─────────────────────────────────────────────────────────────────────────────

async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "bot": "running"})


async def home(request: web.Request) -> web.Response:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>MediaSearchBot</title>
  <style>
    body { margin:0; display:flex; justify-content:center; align-items:center;
           min-height:100vh; background:#0d1117; font-family:sans-serif; color:#e6edf3; }
    .card { text-align:center; padding:40px; border:1px solid #30363d;
            border-radius:12px; background:#161b22; max-width:400px; }
    h1 { font-size:2rem; margin-bottom:8px; }
    p  { color:#8b949e; }
    .badge { display:inline-block; margin-top:20px; padding:8px 20px;
             background:#238636; border-radius:6px; color:#fff;
             text-decoration:none; font-weight:600; }
  </style>
</head>
<body>
  <div class="card">
    <h1>🎬 MediaSearchBot</h1>
    <p>Telegram media search bot is <strong style="color:#3fb950">online</strong> and running.</p>
    <a class="badge" href="/health">Health Check</a>
  </div>
</body>
</html>"""
    return web.Response(text=html, content_type="text/html")


def build_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", home)
    app.router.add_get("/health", health)
    return app

async def keep_alive():
    """
    Pings the bot's own  URL every 10 minutes to prevent it from sleeping.
    Set the URL environment variable to your Render app URL.
    e.g. https://your-app-name.onrender.com
    """
    if not URL:
        logging.info("URL not set — keep-alive ping disabled.")
        return

    url = URL.rstrip("/")
    timeout = ClientTimeout(total=30)
    logging.info(f"Keep-alive started → pinging {url} every 10 minutes.")

    while True:
        await asyncio.sleep(3 * 60)  # wait 3 minutes between pings
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    logging.info(f"Keep-alive ping → {resp.status}")
        except Exception as e:
            logging.warning(f"Keep-alive ping failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Pyrogram Bot
# ─────────────────────────────────────────────────────────────────────────────

class Bot(Client):
    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=50,
            plugins={"root": "plugins"},
            sleep_threshold=60,  # auto-sleep FloodWaits up to 60s
            parse_mode=ParseMode.HTML,
        )

    async def start(self):
        await super().start()
        await Media.ensure_indexes()
        me = await self.get_me()
        self.username = "@" + me.username
        self.mention  = me.mention
        logger.info("✅ %s started as %s", me.first_name, self.username)

        # ── Pre-resolve all peers so Pyrogram caches them ────────────────────
        # Without this, bot.get_chat_member(numeric_id, ...) raises
        # "Peer id invalid" because the peer was never "seen" before.
        peers_to_resolve = list(CHANNELS)
        if AUTH_CHANNEL:
            peers_to_resolve.append(AUTH_CHANNEL)
        if LOG_CHANNEL:
            peers_to_resolve.append(LOG_CHANNEL)

        for peer in peers_to_resolve:
            try:
                await self.get_chat(peer)
                logger.info("✅ Resolved peer: %s", peer)
            except Exception as e:
                logger.warning("⚠️ Could not resolve peer %s: %s", peer, e)
        # ─────────────────────────────────────────────────────────────────────

        if LOG_CHANNEL:
            try:
                await self.send_message(
                    LOG_CHANNEL,
                    f"<b>🤖 {me.mention} started!</b>\n"
                    f"<code>Username:</code> {self.username}"
                )
            except Exception as e:
                logger.warning("Log channel error: %s", e)

    async def stop(self, *args):
        await super().stop()
        logger.info("Bot stopped.")


# ─────────────────────────────────────────────────────────────────────────────
#  Run both concurrently
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    bot    = Bot()
    webapp = build_web_app()
    runner = web.AppRunner(webapp)

    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)

    await bot.start()
    await site.start()
    logger.info("🌐 Web server listening on port %d", PORT)

    # Keep running forever – no sleep(x) that would pause the event loop
    await asyncio.Event().wait()

# Keep Render awake with a self-ping every 10 minutes
    asyncio.create_task(keep_alive())


if __name__ == "__main__":
    asyncio.run(main())
