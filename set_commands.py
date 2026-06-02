"""
set_commands.py  –  Set bot command menu via Telegram Bot API

Run once after deployment (or any time you want to refresh the menu):

    python set_commands.py

Reads BOT_TOKEN from environment (same .env / config vars your bot uses).
Uses the raw Bot API directly — no Pyrogram needed, no extra deps.

Scopes set:
  • default          → commands visible to every user
  • all_private_chats → same (explicit)
  • all_group_chats  → only /start shown to regular users in groups
  • BotCommandScopeChat (admin IDs) → full admin command list
"""

import asyncio
import os
import json
import sys
from typing import Any

import aiohttp  # already in requirements.txt

# ── Config ────────────────────────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    sys.exit("❌  BOT_TOKEN environment variable is not set.")

# Space-separated admin IDs  (same as ADMINS in config.py)
_raw_admins = os.environ.get("ADMINS", "")
ADMIN_IDS: list[int] = [int(x) for x in _raw_admins.split() if x.strip().lstrip("-").isdigit()]

BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Command definitions ───────────────────────────────────────────────────────

# Commands shown to every user (private chat)
USER_COMMANDS = [
    ("start",  "Start the bot / get welcome message"),
    ("help",   "How to search, filter and use the bot"),
]

# Full admin command list (shown only in admin PMs)
ADMIN_COMMANDS = USER_COMMANDS + [
    ("index",           "Index a channel range (wizard)"),
    ("cancelindex",     "Abort a running index wizard"),
    ("setskip",         "Set message-ID offset for indexing"),
    ("total",           "Total files in the database"),
    ("users",           "Total registered users"),
    ("channel",         "List watched/indexed channels"),
    ("delete",          "Remove a file from the database (reply to it)"),
    ("broadcast",       "Broadcast a message to all users"),
    ("cancelbroadcast", "Stop an in-progress broadcast"),
    ("logs",            "Get the bot log file"),
]

# Minimal set shown in groups (full search is text-based, no slash needed)
GROUP_COMMANDS = [
    ("start", "Check bot status / force-subscribe"),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt(cmds: list[tuple[str, str]]) -> list[dict]:
    return [{"command": c, "description": d} for c, d in cmds]


async def _call(session: aiohttp.ClientSession, method: str, payload: dict) -> dict:
    url = f"{BASE}/{method}"
    async with session.post(url, json=payload) as resp:
        data: dict[str, Any] = await resp.json()
    return data


async def _set(session: aiohttp.ClientSession, commands: list[tuple], scope: dict, label: str):
    result = await _call(session, "setMyCommands", {
        "commands": _fmt(commands),
        "scope":    scope,
    })
    status = "✅" if result.get("result") else "❌"
    print(f"  {status}  {label:45s}  →  {result}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    print(f"\n🤖  Setting commands for bot token …{BOT_TOKEN[-6:]}\n")

    async with aiohttp.ClientSession() as session:

        # 1. Default scope – every chat/user not covered by a more specific scope
        await _set(session, USER_COMMANDS,
                   {"type": "default"},
                   "default (all users)")

        # 2. Explicit private chats – same commands, cleaner UX
        await _set(session, USER_COMMANDS,
                   {"type": "all_private_chats"},
                   "all_private_chats")

        # 3. Groups – only /start, search is free-text
        await _set(session, GROUP_COMMANDS,
                   {"type": "all_group_chats"},
                   "all_group_chats")

        # 4. Per-admin private scope – show full admin menu
        if not ADMIN_IDS:
            print("  ⚠️   ADMINS env var not set — skipping per-admin scopes.")
        for admin_id in ADMIN_IDS:
            await _set(session, ADMIN_COMMANDS,
                       {"type": "chat", "chat_id": admin_id},
                       f"admin chat_id={admin_id}")

    print("\n✅  Done!  Open your bot in Telegram and tap the '/' button to verify.\n")


if __name__ == "__main__":
    asyncio.run(main())
