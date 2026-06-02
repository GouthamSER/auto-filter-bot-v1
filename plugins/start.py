"""
plugins/start.py  –  /start · Help · Status
"""

import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
)
from pyrogram.errors import (
    UserNotParticipant,
    ChatAdminRequired,
    PeerIdInvalid,
    ChannelInvalid,
    ChannelPrivate,
)

from config import START_MSG, FORCE_SUB_MSG, AUTH_CHANNEL

logger = logging.getLogger(__name__)

_invite_cache: str = ""
_BACK = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_start")]])


# ─────────────────────────────────────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

async def is_subscribed(bot: Client, user_id: int) -> bool:
    if not AUTH_CHANNEL:
        return True
    try:
        member = await bot.get_chat_member(AUTH_CHANNEL, user_id)
        return member.status not in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT)
    except UserNotParticipant:
        return False
    except (PeerIdInvalid, ChannelInvalid, ChannelPrivate) as e:
        logger.error("AUTH_CHANNEL peer unresolved (%s). Allowing user %s.", e, user_id)
        return True
    except Exception as e:
        logger.exception("is_subscribed error: %s", e)
        return True


async def _get_invite(bot: Client) -> str:
    global _invite_cache
    if _invite_cache:
        return _invite_cache
    try:
        chat = await bot.get_chat(AUTH_CHANNEL)
        _invite_cache = (
            f"https://t.me/{chat.username}" if chat.username
            else await bot.export_chat_invite_link(AUTH_CHANNEL)
        )
    except ChatAdminRequired:
        _invite_cache = "https://t.me"
    except Exception as e:
        logger.warning("Could not get invite link: %s", e)
        _invite_cache = "https://t.me"
    return _invite_cache


def _start_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Search Here", switch_inline_query_current_chat=""),
            InlineKeyboardButton("🌐 Go Inline",   switch_inline_query=""),
        ],
        [
            InlineKeyboardButton("❓ Help",   callback_data="help"),
            InlineKeyboardButton("📊 Status", callback_data="status"),
        ],
    ])


# ─────────────────────────────────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("start") & filters.private)
async def start(bot: Client, message: Message):
    user = message.from_user
    args = message.command[1] if len(message.command) > 1 else None

    # Deep-link: /start subscribe
    if args == "subscribe":
        invite  = await _get_invite(bot)
        buttons = [[InlineKeyboardButton("✅ Join Channel", url=invite)]]
        return await message.reply(FORCE_SUB_MSG, reply_markup=InlineKeyboardMarkup(buttons))

    # Deep-link: /start <file_id>  →  deliver file
    if args and args not in ("start", "help", "status"):
        if not await is_subscribed(bot, user.id):
            invite  = await _get_invite(bot)
            buttons = [[InlineKeyboardButton("✅ Join Channel", url=invite)]]
            return await message.reply(
                FORCE_SUB_MSG + "\n\n<i>After joining, tap the file button again.</i>",
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        from plugins.search import send_file_to_user
        await message.reply("📤 <b>Fetching your file…</b>")
        await send_file_to_user(bot, user.id, args)
        return

    # Normal /start — force-sub check
    if not await is_subscribed(bot, user.id):
        invite  = await _get_invite(bot)
        buttons = [[InlineKeyboardButton("✅ Join Channel", url=invite)]]
        return await message.reply(FORCE_SUB_MSG, reply_markup=InlineKeyboardMarkup(buttons))

    text = START_MSG.format(
        mention    = user.mention,
        username   = bot.username.lstrip("@"),
        first_name = user.first_name,
    )
    await message.reply(text, reply_markup=_start_buttons())


# ─────────────────────────────────────────────────────────────────────────────
#  ⬅️ Back to start
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^back_start$"))
async def back_start_cb(bot: Client, query: CallbackQuery):
    user = query.from_user
    text = START_MSG.format(
        mention    = user.mention,
        username   = bot.username.lstrip("@"),
        first_name = user.first_name,
    )
    try:
        await query.message.edit(text, reply_markup=_start_buttons())
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  ❓ Help
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^help$"))
async def help_cb(bot: Client, query: CallbackQuery):
    uname = bot.username.lstrip("@")
    text = (
        "╔══════════════════════╗\n"
        "      ❓ <b>How To Use</b>\n"
        "╚══════════════════════╝\n\n"

        "💬 <b>Search in PM</b>\n"
        "┗ Just type any <b>movie or file name</b> and tap a result to receive it instantly.\n\n"

        "👥 <b>Search in a Group</b>\n"
        "┗ Type the name in the group → tap a result → file arrives in <b>your PM</b>.\n\n"

        "🔎 <b>Filter by File Type</b>\n"
        "┣ <code>movie name | video</code>\n"
        "┣ <code>song name | audio</code>\n"
        "┗ <code>file name | document</code>\n\n"

        "◀▶ <b>Pagination</b>\n"
        "┗ Use <b>◀ PREV</b> and <b>NEXT ▶</b> — only you can scroll your own results.\n\n"

        "🌐 <b>Inline Mode</b>\n"
        f"┗ Type <code>@{uname} movie name</code> in <b>any chat</b> to search inline.\n\n"

        "⏳ <b>Auto-Delete</b>\n"
        "┗ Files delete after a few minutes — "
        "📌 <b><a href='https://t.me/me'>forward to Saved Messages</a></b> to keep them!"
    )
    await query.message.edit(
        text,
        reply_markup=_BACK,
        disable_web_page_preview=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  📊 Status
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^status$"))
async def status_cb(bot: Client, query: CallbackQuery):
    await query.answer("⏳ Fetching stats…")
    try:
        from database.db import Media, Users, DUAL_DB
        total_files = await Media.count_documents()
        total_users = await Users.count()
    except Exception as e:
        logger.exception("Status fetch error: %s", e)
        return await query.message.edit(
            "❌ Could not fetch stats. Try again later.",
            reply_markup=_BACK,
        )

    me      = await bot.get_me()
    db_mode = "🟡 Dual DB (DB1 + DB2)" if DUAL_DB else "🟢 Single DB"

    text = (
        "╔══════════════════════╗\n"
        "      📊 <b>Bot Status</b>\n"
        "╚══════════════════════╝\n\n"

        f"🤖 <b>Bot:</b> {me.mention}\n"
        f"🔗 <b>Username:</b> @{me.username}\n\n"

        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📁 <b>Total Files:</b>  <code>{total_files:,}</code>\n"
        f"👥 <b>Total Users:</b>  <code>{total_users:,}</code>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        f"🗄 <b>Database:</b>  {db_mode}\n"
        "🟢 <b>Status:</b>  Online & Running"
    )
    await query.message.edit(text, reply_markup=_BACK)
