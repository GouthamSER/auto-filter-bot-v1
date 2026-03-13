"""
plugins/admin.py  –  Admin commands + channel indexer (bot-only, no userbot needed)

Indexing flow:
  • Admin sends a t.me link or forwards a message from a channel
  • Bot asks for confirmation → Accept / Reject
  • On accept: bot.get_messages() in batches indexes all media up to that message ID
  • /setskip N  → start indexing from message N
  • Cancel button aborts mid-index
"""

import logging
import asyncio
import re
import os

from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelInvalid, ChatAdminRequired,
    UsernameInvalid, UsernameNotModified,
)

from config import ADMINS, CHANNELS, LOG_CHANNEL
from database.db import Media, save_file

logger = logging.getLogger(__name__)
_lock = asyncio.Lock()

# ─────────────────────────────────────────────────────────────────────────────
#  FloodWait-safe wrappers
# ─────────────────────────────────────────────────────────────────────────────

async def safe_edit(msg, text: str, reply_markup=None):
    """Edit a message, handling FloodWait by sleeping then retrying once."""
    for attempt in range(2):
        try:
            kwargs = {"text": text}
            if reply_markup:
                kwargs["reply_markup"] = reply_markup
            return await msg.edit(**kwargs)
        except FloodWait as e:
            if attempt == 0:
                logger.warning("FloodWait %ds on edit – sleeping", e.value)
                await asyncio.sleep(min(e.value, 30))
            else:
                logger.error("FloodWait persists on edit, giving up: %s", e)
        except MessageNotModified:
            pass
        except Exception as e:
            logger.warning("safe_edit error: %s", e)
            break


async def safe_reply(message, text: str, reply_markup=None):
    """Reply to a message, handling FloodWait."""
    for attempt in range(2):
        try:
            return await message.reply(text, reply_markup=reply_markup)
        except FloodWait as e:
            if attempt == 0:
                logger.warning("FloodWait %ds on reply – sleeping", e.value)
                await asyncio.sleep(min(e.value, 30))
            else:
                logger.error("FloodWait persists on reply, giving up: %s", e)
        except Exception as e:
            logger.warning("safe_reply error: %s", e)
            break

logger = logging.getLogger(__name__)
_lock = asyncio.Lock()


# ─────────────────────────────────────────────────────────────────────────────
#  Shared runtime state (replaces utils.temp)
# ─────────────────────────────────────────────────────────────────────────────

class _State:
    CANCEL:  bool = False
    CURRENT: int  = 0   # skip offset – set via /setskip

state = _State()


# ─────────────────────────────────────────────────────────────────────────────
#  /setskip  –  set message offset before indexing
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("setskip") & filters.user(ADMINS))
async def set_skip(bot: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply(
            f"Usage: <code>/setskip 1000</code>\n\n"
            f"Current skip: <code>{state.CURRENT}</code>"
        )
    try:
        state.CURRENT = int(message.command[1])
        await message.reply(f"✅ Skip set to <code>{state.CURRENT}</code>")
    except ValueError:
        await message.reply("⚠️ Skip number must be an integer.")


# ─────────────────────────────────────────────────────────────────────────────
#  /index  –  step-by-step: ask first link, then last link, then confirm
# ─────────────────────────────────────────────────────────────────────────────

_LINK_RE = re.compile(
    r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$"
)

# Conversation state per admin user: {"step": "first"|"last", "chat": ..., "first_id": ...}
_index_state: dict[int, dict] = {}


def _parse_link(text: str):
    """Return (chat_id, msg_id) or (None, None) if invalid."""
    match = _LINK_RE.search(text.strip())
    if not match:
        return None, None
    chat_id = match.group(4)
    msg_id  = int(match.group(5))
    if chat_id.isnumeric():
        chat_id = int("-100" + chat_id)
    return chat_id, msg_id


@Client.on_message(filters.command("index") & filters.user(ADMINS))
async def index_cmd(bot: Client, message: Message):
    """Start the index wizard."""
    if _lock.locked():
        return await safe_reply(message, "⏳ An index is already running. Wait for it to finish.")

    _index_state[message.from_user.id] = {"step": "first"}
    await safe_reply(
        message,
        "📥 <b>Step 1/2 — First Message</b>\n\n"
        "Send me the <b>link of the first file</b> in the channel you want to index.\n\n"
        "Example: <code>https://t.me/c/1234567890/1</code>\n\n"
        "Send /cancelindex to abort."
    )


@Client.on_message(filters.command("cancelindex") & filters.user(ADMINS))
async def cancel_index_wizard(bot: Client, message: Message):
    _index_state.pop(message.from_user.id, None)
    await safe_reply(message, "❌ Index wizard cancelled.")


@Client.on_message(filters.text & filters.private & filters.user(ADMINS))
async def index_wizard_handler(bot: Client, message: Message):
    """Handle the two-step link collection for /index."""
    uid = message.from_user.id
    if uid not in _index_state:
        return   # not in wizard, let other handlers deal with it

    step = _index_state[uid].get("step")
    text = message.text.strip()

    # ── Step 1: First message link ────────────────────────────────────────────
    if step == "first":
        chat_id, first_msg_id = _parse_link(text)
        if not chat_id:
            return await safe_reply(message,
                "❌ Invalid link. Send a valid t.me message link.\n"
                "Example: <code>https://t.me/c/1234567890/1</code>"
            )

        # Validate access
        try:
            await bot.get_chat(chat_id)
        except ChannelInvalid:
            _index_state.pop(uid, None)
            return await safe_reply(message,
                "⚠️ Cannot access that channel. Make me an <b>admin</b> there first."
            )
        except Exception as e:
            _index_state.pop(uid, None)
            return await safe_reply(message, f"❌ Error: <code>{e}</code>")

        try:
            m = await bot.get_messages(chat_id, first_msg_id)
            if m.empty:
                return await safe_reply(message, "⚠️ That message is empty or deleted. Send a valid first message link.")
        except Exception:
            _index_state.pop(uid, None)
            return await safe_reply(message,
                "⚠️ Could not fetch that message. Make sure I am an admin in the channel."
            )

        _index_state[uid] = {"step": "last", "chat": chat_id, "first_id": first_msg_id}
        await safe_reply(
            message,
            f"✅ <b>First message set!</b>\n"
            f"🔗 Chat: <code>{chat_id}</code>\n"
            f"📌 First ID: <code>{first_msg_id}</code>\n\n"
            "📥 <b>Step 2/2 — Last Message</b>\n\n"
            "Now send the <b>link of the last file</b> (most recent one) to index up to.\n\n"
            "Send /cancelindex to abort."
        )

    # ── Step 2: Last message link ─────────────────────────────────────────────
    elif step == "last":
        chat_id   = _index_state[uid]["chat"]
        first_id  = _index_state[uid]["first_id"]

        link_chat, last_msg_id = _parse_link(text)
        if not link_chat:
            return await safe_reply(message,
                "❌ Invalid link. Send a valid t.me message link.\n"
                "Example: <code>https://t.me/c/1234567890/500</code>"
            )

        # Ensure same channel
        if str(link_chat) != str(chat_id):
            return await safe_reply(message,
                f"⚠️ This link is from a different channel (<code>{link_chat}</code>).\n"
                f"Send a link from <code>{chat_id}</code>."
            )

        if last_msg_id < first_id:
            # swap silently so order doesn't matter
            first_id, last_msg_id = last_msg_id, first_id

        total_range = last_msg_id - first_id + 1
        _index_state.pop(uid, None)   # clear state

        buttons = [[
            InlineKeyboardButton(
                "✅ Start Indexing",
                callback_data=f"index#accept#{chat_id}#{first_id}#{last_msg_id}#{uid}"
            ),
            InlineKeyboardButton("❌ Cancel", callback_data="close_data"),
        ]]
        await safe_reply(
            message,
            f"🗂 <b>Confirm Indexing</b>\n\n"
            f"📡 Channel: <code>{chat_id}</code>\n"
            f"📌 From ID: <code>{first_id}</code>\n"
            f"📌 To ID:   <code>{last_msg_id}</code>\n"
            f"📊 Range:   <code>{total_range}</code> messages\n\n"
            "Tap <b>Start Indexing</b> to begin.",
            reply_markup=InlineKeyboardMarkup(buttons),
        )


# ─────────────────────────────────────────────────────────────────────────────
#  Callback: index#accept / index#reject / index_cancel
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^index"))
async def index_callback(bot: Client, query: CallbackQuery):

    # Cancel mid-index
    if query.data == "index_cancel":
        state.CANCEL = True
        return await query.answer("⛔ Cancelling…", show_alert=True)

    parts = query.data.split("#")
    # format: index#accept#chat#first_id#last_id#from_user
    _, action, chat, first_id, last_id, from_user = parts
    from_user_id = int(from_user)
    first_msg_id = int(first_id)
    last_msg_id  = int(last_id)

    # Reject (unused in new flow but kept for safety)
    if action == "reject":
        await query.message.delete()
        return

    # Already running?
    if _lock.locked():
        return await query.answer("⏳ Another index is already running. Please wait.", show_alert=True)

    await query.answer("⏳ Starting…", show_alert=True)

    await query.message.edit(
        f"⏳ <b>Indexing started…</b>\n\n"
        f"📡 Channel: <code>{chat}</code>\n"
        f"📌 From: <code>{first_msg_id}</code> → To: <code>{last_msg_id}</code>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("⛔ Cancel", callback_data="index_cancel")]]
        ),
    )

    try:
        chat = int(chat)
    except ValueError:
        pass

    await _index_to_db(first_msg_id, last_msg_id, chat, query.message, bot)


# ─────────────────────────────────────────────────────────────────────────────
#  Close button
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^close_data$"))
async def close_cb(bot: Client, query: CallbackQuery):
    await query.message.delete()


# ─────────────────────────────────────────────────────────────────────────────
#  Core indexing loop  (bot.iter_messages – no userbot needed)
# ─────────────────────────────────────────────────────────────────────────────

async def _index_to_db(first_msg_id: int, last_msg_id: int, chat, msg, bot: Client):
    total_files = 0
    duplicate   = 0
    errors      = 0
    deleted     = 0
    no_media    = 0
    unsupported = 0
    current     = 0

    # Fetch in batches of 200 IDs from last_msg_id down to first_msg_id (inclusive)
    BATCH = 200
    import time
    last_edit_ts = 0.0

    async with _lock:
        try:
            state.CANCEL = False

            start = last_msg_id
            stop  = first_msg_id - 1   # inclusive: we want first_msg_id included

            while start > stop:
                if state.CANCEL:
                    await safe_edit(
                        msg,
                        "⛔ <b>Indexing cancelled!</b>\n\n"
                        + _stats(total_files, duplicate, deleted, no_media, unsupported, errors)
                    )
                    return

                # Build a batch of IDs (high → low)
                batch_end = max(stop, start - BATCH)
                ids       = list(range(start, batch_end, -1))
                start     = batch_end

                # Fetch batch
                try:
                    messages = await bot.get_messages(chat, ids)
                except FloodWait as e:
                    wait = e.value + 2
                    logger.warning("FloodWait %ds on get_messages – sleeping", wait)
                    await asyncio.sleep(wait)
                    try:
                        messages = await bot.get_messages(chat, ids)
                    except Exception as e2:
                        logger.error("Retry failed: %s", e2)
                        errors += len(ids)
                        continue
                except Exception as e:
                    logger.exception("get_messages error: %s", e)
                    errors += len(ids)
                    continue

                for message in messages:
                    if state.CANCEL:
                        await safe_edit(
                            msg,
                            "⛔ <b>Indexing cancelled!</b>\n\n"
                            + _stats(total_files, duplicate, deleted, no_media, unsupported, errors)
                        )
                        return

                    current += 1

                    if not message or message.empty:
                        deleted += 1
                        continue
                    if not message.media:
                        no_media += 1
                        continue
                    if message.media not in (
                        enums.MessageMediaType.VIDEO,
                        enums.MessageMediaType.AUDIO,
                        enums.MessageMediaType.DOCUMENT,
                    ):
                        unsupported += 1
                        continue

                    media = getattr(message, message.media.value, None)
                    if not media:
                        unsupported += 1
                        continue

                    media.file_type = message.media.value
                    media.caption   = message.caption

                    saved = await save_file(media)
                    if saved:
                        total_files += 1
                    else:
                        duplicate += 1

                # Update progress once per batch (≤1 edit per ~200 messages)
                # and only if at least 5 seconds have passed since last edit
                now = time.time()
                if now - last_edit_ts >= 5:
                    await safe_edit(
                        msg,
                        f"⏳ <b>Indexing…</b>\n\n"
                        f"Fetched: <code>{current}</code>\n"
                        + _stats(total_files, duplicate, deleted, no_media, unsupported, errors),
                        reply_markup=InlineKeyboardMarkup(
                            [[InlineKeyboardButton("⛔ Cancel", callback_data="index_cancel")]]
                        ),
                    )
                    last_edit_ts = time.time()

        except Exception as e:
            logger.exception("Index error: %s", e)
            await safe_edit(msg, f"❌ Error: <code>{e}</code>")
            return

        await safe_edit(
            msg,
            "✅ <b>Indexing complete!</b>\n\n"
            + _stats(total_files, duplicate, deleted, no_media, unsupported, errors)
        )


def _stats(files, dup, deleted, no_media, unsupported, errors) -> str:
    return (
        f"💾 Saved: <code>{files}</code>\n"
        f"🔁 Duplicates skipped: <code>{dup}</code>\n"
        f"🗑 Deleted messages: <code>{deleted}</code>\n"
        f"📭 No media: <code>{no_media + unsupported}</code> "
        f"(unsupported: <code>{unsupported}</code>)\n"
        f"❗ Errors: <code>{errors}</code>"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Other admin commands
# ─────────────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("total") & filters.user(ADMINS))
async def total_files(bot: Client, message: Message):
    msg = await safe_reply(message, "⏳ Counting…")
    if not msg:
        return
    try:
        n = await Media.count_documents()
        await safe_edit(msg, f"📦 <b>Total files in database:</b> <code>{n}</code>")
    except Exception as e:
        await safe_edit(msg, f"Error: <code>{e}</code>")


@Client.on_message(filters.command("channel") & filters.user(ADMINS))
async def channel_info(bot: Client, message: Message):
    if not CHANNELS:
        return await safe_reply(message, "No channels configured.")
    lines = ["📑 <b>Watched Channels</b>\n"]
    for ch in CHANNELS:
        try:
            chat = await bot.get_chat(ch)
            name = "@" + chat.username if chat.username else chat.title or str(ch)
        except Exception:
            name = str(ch)
        lines.append(f"• {name}")
    lines.append(f"\n<b>Total:</b> {len(CHANNELS)}")
    text = "\n".join(lines)
    if len(text) < 4096:
        await safe_reply(message, text)
    else:
        path = "/tmp/channels.txt"
        with open(path, "w") as f:
            f.write(text)
        try:
            await message.reply_document(path)
        except FloodWait as e:
            await asyncio.sleep(min(e.value, 30))
            await message.reply_document(path)
        finally:
            os.remove(path)


@Client.on_message(filters.command("delete") & filters.user(ADMINS))
async def delete_file_cmd(bot: Client, message: Message):
    reply = message.reply_to_message
    if not (reply and reply.media):
        return await safe_reply(message, "⚠️ Reply to a media file with /delete.")
    msg = await safe_reply(message, "⏳ Processing…")
    if not msg:
        return
    for ftype in ("document", "video", "audio"):
        media = getattr(reply, ftype, None)
        if media:
            result = await Media.delete_one({"file_name": media.file_name, "file_size": media.file_size})
            if result.deleted_count:
                return await safe_edit(msg, "✅ Removed from database.")
            return await safe_edit(msg, "❌ File not found in database.")
    await safe_edit(msg, "⚠️ Unsupported file type.")


@Client.on_message(filters.command(["logs", "logger"]) & filters.user(ADMINS))
async def send_logs(bot: Client, message: Message):
    try:
        await message.reply_document("TelegramBot.log")
    except FloodWait as e:
        await asyncio.sleep(min(e.value, 30))
        try:
            await message.reply_document("TelegramBot.log")
        except Exception as e2:
            await safe_reply(message, f"FloodWait active, try again later: <code>{e2}</code>")
    except FileNotFoundError:
        await safe_reply(message, "No log file found.")
    except Exception as e:
        await safe_reply(message, str(e))


@Client.on_message(filters.command("users") & filters.user(ADMINS))
async def total_users(bot: Client, message: Message):
    from database.db import Users
    msg = await safe_reply(message, "⏳ Counting users…")
    if not msg:
        return
    try:
        n = await Users.count()
        await safe_edit(
            msg,
            f"👥 <b>Total registered users:</b> <code>{n}</code>\n\n"
            f"Use /broadcast to send a message to all of them."
        )
    except Exception as e:
        await safe_edit(msg, f"Error: <code>{e}</code>")
