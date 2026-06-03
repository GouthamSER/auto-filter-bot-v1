"""
plugins/search.py  –  Search in PM and Groups

PM flow:
  User types name → result buttons (callback) → tap → file sent in PM → auto-delete

Group flow:
  User types name → result buttons shown IN GROUP with URL deep-links
  User taps file  → redirected to bot PM via  t.me/bot?start=<file_id>
  /start handler  → detects file_id, sends file → auto-delete
  Pagination (◀ PREV / NEXT ▶) still works in group via callbacks

Security:
  PREV/NEXT callbacks are restricted to the user who triggered the search.
  send# callbacks are restricted to the user who taps (already safe by design
  since the file is sent to query.from_user.id, not the message owner).
"""

import asyncio
import logging
import math
import os
import re

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import AUTH_CHANNEL, MAX_RESULTS, USE_CAPTION_FILTER
from database.db import _col, get_search_results
from .start import is_subscribed, _get_invite

logger = logging.getLogger(__name__)

AUTO_DELETE_TIME = int(os.environ.get("AUTO_DELETE_TIME", 300))

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_size(size: int) -> str:
    s = float(size or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if s < 1024:
            return f"{s:.2f} {unit}" if unit in ("MB", "GB", "TB") else f"{s:.0f} {unit}"
        s /= 1024
    return f"{s:.2f} TB"


def _file_emoji(ftype: str) -> str:
    return {"video": "🎬", "audio": "🎵", "document": "📁"}.get(ftype or "", "📁")


def _build_label(name: str, size: str, ftype: str) -> str:
    """[1.59 GB]- 🎬 -Filename truncated…"""
    emoji  = _file_emoji(ftype)
    prefix = f"[{size}]- {emoji} -"
    max_name = 64 - len(prefix)
    if len(name) > max_name:
        name = name[:max_name - 1] + "…"
    return f"{prefix}{name}"


def _parse_query(text: str):
    if "|" in text:
        q, ft = text.split("|", 1)
        return q.strip(), ft.strip().lower() or None
    return text.strip(), None


def _build_keyboard(
    files: list,
    query: str,          # raw query (may include "| filetype")
    offset: int,
    total: int,
    user_id: int,        # owner of this search – encoded in nav callbacks
    bot_username: str = None,   # if set → group mode: URL deep-link buttons
) -> InlineKeyboardMarkup:
    rows = []
    in_group = bool(bot_username)

    for f in files:
        name   = f.get("file_name", "Unknown")
        size   = _fmt_size(f.get("file_size", 0))
        ftype  = f.get("file_type") or "document"
        fid    = f["file_id"]
        label  = _build_label(name, size, ftype)

        if in_group:
            # Deep-link: clicking opens bot PM and triggers /start <file_id>
            rows.append([InlineKeyboardButton(
                label,
                url=f"https://t.me/{bot_username}?start={fid}"
            )])
        else:
            rows.append([InlineKeyboardButton(label, callback_data=f"send#{fid}")])

    # Pagination row – always callback (works in both PM and group)
    # FIX: encode user_id in callback so only the search owner can paginate
    page_size    = MAX_RESULTS
    current_page = (offset // page_size) + 1
    total_pages  = max(1, math.ceil(total / page_size))

    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            "◀ PREV", callback_data=f"page#{user_id}#{query}#{offset - page_size}"
        ))
    nav.append(InlineKeyboardButton(
        f"🗂 {current_page}/{total_pages}", callback_data="noop"
    ))
    if total > offset + page_size:
        nav.append(InlineKeyboardButton(
            "NEXT ▶", callback_data=f"page#{user_id}#{query}#{offset + page_size}"
        ))
    rows.append(nav)
    return InlineKeyboardMarkup(rows)


def _search_text(query: str, total: int, in_group: bool = False) -> str:
    suffix = "\n👇 <i>Tap a file → you'll be taken to my PM where it will be sent!</i>" \
             if in_group else \
             "\n👇 <i>Tap a file name to receive it here:</i>"
    return (
        f"<blockquote>🔎 <b>Results for:</b> <code>{query}</code>\n📁 <b>Found:</b> <code>{total}</code> file(s){suffix}</blockquote>"
    )

async def _count(query: str, file_type: str = None) -> int:
    query = query.strip()
    if not query:
        raw = "."
    elif " " not in query:
        raw = r"(\b|[\.+\-_])" + re.escape(query) + r"(\b|[\.+\-_])"
    else:
        raw = re.escape(query).replace(r"\ ", r".*[\s\.+\-_()\[\]]")
    try:
        regex = re.compile(raw, flags=re.IGNORECASE)
    except re.error:
        return 0
    filt = (
        {"$or": [{"file_name": regex}, {"caption": regex}]}
        if USE_CAPTION_FILTER
        else {"file_name": regex}
    )
    if file_type:
        filt["file_type"] = file_type
    return await _col.count_documents(filt)


async def _schedule_delete(*msgs, delay: int = AUTO_DELETE_TIME):
    await asyncio.sleep(delay)
    for m in msgs:
        try:
            await m.delete()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  Send file helper  (used by both /start deep-link and send# callback)
# ─────────────────────────────────────────────────────────────────────────────

async def send_file_to_user(bot: Client, user_id: int, file_id: str):
    """Fetch file from DB, send to user_id, schedule auto-delete."""
    doc = await _col.find_one({"file_id": file_id})
    if not doc:
        await bot.send_message(user_id, "⚠️ <b>File not found in database.</b>")
        return

    fname = doc.get("file_name", "Unknown")
    fsize = _fmt_size(doc.get("file_size", 0))
    ftype = doc.get("file_type", "document")
    emoji = _file_emoji(ftype)

    caption = (
        f"<blockquote>{emoji} <b>{fname}</b>\n"
        f"📦 <b>Size:</b> <code>{fsize}</code>\n"
        f"🗂 <b>Type:</b> {ftype.capitalize()}</blockquote>\n\n"
        f"⚠️ <i>This file will be <b>auto-deleted in "
        f"{AUTO_DELETE_TIME // 60} minute(s)</b> to avoid copyright issues.</i>\n"
        f"📌 <b>Forward it to your Saved Messages to keep it forever!</b>"
    )

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("💾 Save to Saved Messages", callback_data=f"save#{file_id}")
    ]])

    try:
        if ftype == "video":
            sent = await bot.send_video(user_id, video=file_id,
                                        caption=caption, reply_markup=markup)
        elif ftype == "audio":
            sent = await bot.send_audio(user_id, audio=file_id,
                                        caption=caption, reply_markup=markup)
        else:
            sent = await bot.send_document(user_id, document=file_id,
                                           caption=caption, reply_markup=markup)

        timer = await bot.send_message(
            user_id,
            f"<blockquote>⏳ <b>Auto-deletes in {AUTO_DELETE_TIME // 60} min(s).</b>\n"
            f"📌 Forward to <a href='https://t.me/me'>Saved Messages</a> to keep it!</blockquote>"
        )
        asyncio.create_task(_schedule_delete(sent, timer, delay=AUTO_DELETE_TIME))

    except FloodWait as e:
        # NEVER send another message during FloodWait — it cascades into a longer ban
        logger.warning(
            "FloodWait %ds while sending file to %s — skipping error message to avoid cascade",
            e.value, user_id
        )
    except Exception as e:
        logger.exception("send_file_to_user error: %s", e)
        try:
            await bot.send_message(user_id, f"❌ Failed to send file: <code>{e}</code>")
        except FloodWait:
            pass
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
#  Search handler  (PM + Group)
# ─────────────────────────────────────────────────────────────────────────────

_IGNORE_CMDS = ["start", "help", "index", "total", "delete",
                "channel", "logger", "logs", "broadcast", "setskip"]


@Client.on_message(
    filters.text
    & (filters.private | filters.group)
    & ~filters.command(_IGNORE_CMDS)
)
async def search_handler(bot: Client, message: Message):
    text = message.text.strip()
    if not text or text.startswith("/"):
        return

    user  = message.from_user
    in_pm = message.chat.type == ChatType.PRIVATE

    # Force-subscribe check
    if not await is_subscribed(bot, user.id):
        from config import FORCE_SUB_MSG
        invite  = await _get_invite(bot)
        buttons = [[InlineKeyboardButton("✅ Join Channel", url=invite)]]
        reply   = await message.reply(FORCE_SUB_MSG, reply_markup=InlineKeyboardMarkup(buttons))
        if not in_pm:
            asyncio.create_task(_schedule_delete(message, reply, delay=30))
        return

    query, file_type = _parse_query(text)
    if not query:
        return

    processing = await message.reply("⚡ Processing Request\n\n🔎 Searching available files...\n⏳ This may take a few seconds.")
    files, _ = await get_search_results(query, file_type=file_type,
                                        max_results=MAX_RESULTS, offset=0)
    if not files:
        try:
            no_res = await processing.edit(
                f"🎬 No Matching Files Found\n\n"
              f"🔍 Query: {query}\n\n"
              "📂 This title is currently unavailable.\n\n"
              "💡 Try:\n"
              "• Movie name only\n"
              "• Alternate title\n"
              "• Release year\n"
              "• Correct spelling"
            )
            if not in_pm:
                asyncio.create_task(_schedule_delete(message, no_res, delay=30))
        except FloodWait:
            pass
        except Exception:
            pass
        return

    total    = await _count(query, file_type)
    username = bot.username.lstrip("@") if not in_pm else None
    # FIX: pass user.id so only the requester can use PREV/NEXT
    keyboard = _build_keyboard(files, text, 0, total,
                               user_id=user.id, bot_username=username)

    try:
        await processing.edit(
            _search_text(query, total, in_group=not in_pm),
            reply_markup=keyboard,
        )
    except FloodWait:
        pass
    except Exception:
        pass

    asyncio.create_task(_schedule_delete(message, processing, delay=AUTO_DELETE_TIME))


# ─────────────────────────────────────────────────────────────────────────────
#  Callback – paginate  (group pagination rebuilds with URL buttons)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^page#"))
async def page_cb(bot: Client, query: CallbackQuery):
    # FIX: format is now page#<user_id>#<raw_query>#<offset>
    # Split into exactly 4 parts (query may contain "#" itself – unlikely but safe)
    parts = query.data.split("#", 3)
    if len(parts) != 4:
        return await query.answer("Invalid pagination data.", show_alert=True)

    _, owner_id, raw_query, raw_offset = parts

    # ── SECURITY: only the user who triggered the search can paginate ──
    if query.from_user.id != int(owner_id):
        return await query.answer(
            "⚠️ Only the person who searched can use these buttons.",
            show_alert=True
        )

    offset   = int(raw_offset)
    q, ft    = _parse_query(raw_query)
    in_group = query.message.chat.type != ChatType.PRIVATE

    files, _ = await get_search_results(q, file_type=ft, max_results=MAX_RESULTS, offset=offset)
    if not files:
        return await query.answer("No more results!", show_alert=True)

    total    = await _count(q, ft)
    username = bot.username.lstrip("@") if in_group else None
    keyboard = _build_keyboard(files, raw_query, offset, total,
                               user_id=int(owner_id), bot_username=username)

    try:
        await query.message.edit_reply_markup(keyboard)
    except MessageNotModified:
        pass
    await query.answer()


# ─────────────────────────────────────────────────────────────────────────────
#  Callback – send file (PM only, groups use URL deep-link instead)
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^send#"))
async def send_file_cb(bot: Client, query: CallbackQuery):
    _, file_id = query.data.split("#", 1)
    await query.answer("📤 Sending…")
    await send_file_to_user(bot, query.from_user.id, file_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Callback – save to saved messages
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^save#"))
async def save_message_cb(bot: Client, query: CallbackQuery):
    """Handle save to saved messages button tap - provides instructions to user."""
    _, file_id = query.data.split("#", 1)

    user_id  = query.from_user.id
    username = query.from_user.username or query.from_user.first_name

    logger.info("User %s (%s) tapped save button for file %s", user_id, username, file_id)

    await query.answer(
        "💾 To save: Long press the message above → Forward → Saved Messages",
        show_alert=True
    )


# ─────────────────────────────────────────────────────────────────────────────
#  No-op
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^noop$"))
async def noop_cb(bot: Client, query: CallbackQuery):
    await query.answer()
