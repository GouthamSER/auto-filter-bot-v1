import logging
import asyncio
import os

from aiohttp import web, ClientSession, ClientTimeout
from pyrogram import Client
from pyrogram.enums import ParseMode

# Assuming these are in your config.py
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

# ── Environment Variables ────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8080))
# If URL is not in config, it will try to get it from Environment Variables
APP_URL = URL or os.environ.get("URL")

# ─────────────────────────────────────────────────────────────────────────────
#  Web server app
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
    Pings the bot's own URL every 3-5 minutes to prevent sleep.
    """
    if not APP_URL:
        logger.info("URL not set — keep-alive ping disabled.")
        return

    url = APP_URL.rstrip("/")
    timeout = ClientTimeout(total=20)
    logger.info(f"Keep-alive started → pinging {url} every 3 minutes.")

    while True:
        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    logger.info(f"Keep-alive ping → Status: {resp.status}")
        except Exception as e:
            logger.warning(f"Keep-alive ping failed: {e}")
        
        # Wait 3 minutes between pings
        await asyncio.sleep(180)

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
            sleep_threshold=60,
            parse_mode=ParseMode.HTML,
        )

    async def start(self):
        await super().start()
        await Media.ensure_indexes()
        me = await self.get_me()
        self.username = "@" + me.username
        self.mention  = me.mention
        logger.info("✅ %s started as %s", me.first_name, self.username)

        # Pre-resolve peers
        peers_to_resolve = list(CHANNELS)
        if AUTH_CHANNEL: peers_to_resolve.append(AUTH_CHANNEL)
        if LOG_CHANNEL: peers_to_resolve.append(LOG_CHANNEL)

        for peer in peers_to_resolve:
            try:
                await self.get_chat(peer)
                logger.info("✅ Resolved peer: %s", peer)
            except Exception as e:
                logger.warning("⚠️ Could not resolve peer %s: %s", peer, e)

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
#  Main Execution
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    bot    = Bot()
    webapp = build_web_app()
    runner = web.AppRunner(webapp)

    # 1. Setup Web Server
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("🌐 Web server listening on port %d", PORT)

    # 2. Start Pyrogram Bot
    await bot.start()

    # 3. Start Keep-Alive Background Task
    # (Must be done BEFORE the blocking Event().wait())
    asyncio.create_task(keep_alive())

    # 4. Keep the loop running forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Process interrupted by user.")
