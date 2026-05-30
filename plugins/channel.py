"""
plugins/channel.py  –  Auto-save files posted in watched CHANNELS
"""

import logging

from pyrogram import Client, filters
from config import CHANNELS
from database.db import save_file

logger = logging.getLogger(__name__)

media_filter = filters.document | filters.video | filters.audio


# FIX: filters.chat([]) crashes Pyrogram when CHANNELS is empty.
# Guard the handler registration so it only fires when channels are configured.
if CHANNELS:
    @Client.on_message(filters.chat(CHANNELS) & media_filter)
    async def auto_index(bot: Client, message):
        """Automatically index every media file posted in watched channels."""
        for ftype in ("document", "video", "audio"):
            media = getattr(message, ftype, None)
            if media is not None:
                media.file_type = ftype
                media.caption   = message.caption
                saved = await save_file(media)
                if saved:
                    logger.info("Auto-indexed: %s", getattr(media, "file_name", ftype))
                return
else:
    logger.warning("CHANNELS is empty — auto-indexing disabled.")
