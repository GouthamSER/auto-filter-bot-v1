"""
plugins/start.py  –  /start command + deep-link file delivery

Buttons on start:
  [🔍 Search Here]  [🌐 Go Inline]
  [❓ Help]         [📊 Status]

Help page  → how to use the bot
Status page → total files + total users (live from DB)
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
            InlineKeyboardButton("Update Channel ⚠", url='t.me/wudixh15'),
            InlineKeyboardButton("Admin 👮‍♂️", url='t.me/im_goutham_josh')
        ],
        [
            InlineKeyboardButton("Help ⚙", callback_data="help"),
            InlineKeyboardButton("Stats 📊", callback_data="status")
        ]
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
        await message.answer("📤 <b>Fetching your file…</b>")
        await send_file_to_user(bot, user.id, args)
        return

    # Normal /start
    if not await is_subscribed(bot, user.id):
        invite  = await _get_invite(bot)
        buttons = [[InlineKeyboardButton("✅ Join Channel", url=invite)]]
        return await message.reply(FORCE_SUB_MSG, reply_markup=InlineKeyboardMarkup(buttons))

    text = START_MSG.format(
        uname      = bot.username.lstrip("@"),
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
        uname      = bot.username.lstrip("@"),
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
      "📚 Search Help \n"
      "Movies: Movie Year → RRR 2022 Series: Name Sxx / SxxExx → Kurukshetra S01E05\n"
      "Tip: add quality/lang → 1080p Tamil Hindi\n"
      "🍿 Send your query now!"
    )
    await query.message.edit(
        text,
        reply_markup=_BACK,
        disable_web_page_preview=True
    )

@Client.on_message(filters.command("help") & filters.private)
async def help_cb(bot: Client, query: CallbackQuery):
    uname = bot.username.lstrip("@")
    text = (
      "📚 Search Help \n"
      "Movies: Movie Year → RRR 2022 Series: Name Sxx / SxxExx → Kurukshetra S01E05\n"
      "Tip: add quality/lang → 1080p Tamil Hindi\n"
      "🍿 Send your query now!"
    )
    await query.message.edit(
        text,
        reply_markup=_BACK,
        disable_web_page_preview=True
    )

# ─────────────────────────────────────────────────────────────────────────────
#  📊 Status
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^status$"))
async def status_cb(bot: Client, query: CallbackQuery):
    await query.answer()
    try:
        from database.db import Media, Users
        total_files = await Media.count_documents()
        total_users = await Users.count()
    except Exception:
        return await query.message.edit(
            "<b>Unable to fetch statistics.</b>",
            reply_markup=_BACK
        )
    me = await bot.get_me()
    text = (
        "<b>Bot Statistics</b>\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"<b>Bot:</b> {me.mention}\n"
        f"<b>Username:</b> @{me.username}\n\n"
        f"<b>Files Indexed:</b> <code>{total_files:,}</code>\n"
        f"<b>Users:</b> <code>{total_users:,}</code>\n\n"
        "<b>System Status:</b> Online"
    )
    await query.message.edit(text, reply_markup=_BACK)
