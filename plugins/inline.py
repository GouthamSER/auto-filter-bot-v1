"""
plugins/inline.py  –  Inline query handler (search via @bot in any chat)
"""

import logging
from urllib.parse import quote

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultCachedDocument,
    InlineQueryResultCachedVideo,
    InlineQueryResultCachedAudio,
)

from config import CACHE_TIME, AUTH_USERS, AUTH_CHANNEL, MAX_RESULTS
from database.db import get_search_results
from .start import is_subscribed

logger = logging.getLogger(__name__)
cache_time = 0 if (AUTH_USERS or AUTH_CHANNEL) else CACHE_TIME


# ─────────────────────────────────────────────────────────────────────────────
# FIX: filters.user(AUTH_USERS) crashes when AUTH_USERS is an empty list because
# Pyrogram doesn't accept an empty user filter. Guard it properly.
# ─────────────────────────────────────────────────────────────────────────────

def _inline_filter():
    if AUTH_USERS:
        return filters.user(AUTH_USERS)
    return None   # no restriction – handled inside the handler


_ifilter = _inline_filter()

if _ifilter is not None:
    @Client.on_inline_query(_ifilter)
    async def answer_inline(bot: Client, query):
        await _handle_inline(bot, query)
else:
    @Client.on_inline_query()
    async def answer_inline(bot: Client, query):
        await _handle_inline(bot, query)


async def _handle_inline(bot, query):
    """Return cached file results for inline queries."""

    if AUTH_CHANNEL and not await is_subscribed(bot, query.from_user.id):
        await query.answer(
            results=[],
            cache_time=0,
            switch_pm_text="⚠️ Join channel to search",
            switch_pm_parameter="subscribe",
        )
        return

    raw_q = query.query.strip()

    if "|" in raw_q:
        text, file_type = raw_q.split("|", 1)
        text      = text.strip()
        file_type = file_type.strip().lower() or None
    else:
        text      = raw_q
        file_type = None

    offset   = int(query.offset or 0)
    files, next_offset = await get_search_results(
        text, file_type=file_type, max_results=MAX_RESULTS, offset=offset
    )

    results      = []
    share_markup = _share_markup(bot.username, text)

    for f in files:
        fid   = f.get("file_id", "")
        fname = f.get("file_name", "Unknown")
        size  = _fmt_size(f.get("file_size", 0))
        ftype = f.get("file_type", "document")
        cap   = f.get("caption") or ""
        desc  = f"Size: {size}  │  Type: {ftype}"

        try:
            if ftype == "video":
                results.append(InlineQueryResultCachedVideo(
                    video_file_id=fid,
                    title=fname,
                    description=desc,
                    caption=cap,
                    reply_markup=share_markup,
                ))
            elif ftype == "audio":
                results.append(InlineQueryResultCachedAudio(
                    audio_file_id=fid,
                    title=fname,
                    caption=cap,
                    reply_markup=share_markup,
                ))
            else:
                results.append(InlineQueryResultCachedDocument(
                    document_file_id=fid,
                    title=fname,
                    description=desc,
                    caption=cap,
                    reply_markup=share_markup,
                ))
        except Exception as e:
            logger.warning("Inline result error for %s: %s", fname, e)
            continue

    if results:
        pm_text = "📁 Results"
        if text:
            pm_text += f" for {text[:30]}"
        await query.answer(
            results=results,
            cache_time=cache_time,
            switch_pm_text=pm_text,
            switch_pm_parameter="start",
            next_offset=str(next_offset) if next_offset != "" else "",
        )
    else:
        pm_text = f'❌ No results for "{text}"' if text else "❌ No files found"
        await query.answer(
            results=[],
            cache_time=cache_time,
            switch_pm_text=pm_text,
            switch_pm_parameter="start",
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _share_markup(username: str, query: str) -> InlineKeyboardMarkup:
    url = "https://t.me/share/url?url=" + quote(f"https://t.me/{username.lstrip('@')}")
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 Search Again", switch_inline_query_current_chat=query),
        InlineKeyboardButton("📤 Share Bot", url=url),
    ]])


def _fmt_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    s = float(size or 0)
    for u in units[:-1]:
        if s < 1024:
            return f"{s:.1f} {u}"
        s /= 1024
    return f"{s:.1f} GB"
