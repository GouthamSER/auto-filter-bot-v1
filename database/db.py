"""
database/db.py  –  All MongoDB interactions for MediaSearchBot
Uses motor (async pymongo) directly — no umongo dependency needed.
"""

import re
import logging
import base64
from struct import pack

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from pyrogram import raw
from pyrogram.file_id import FileId, FileType, PHOTO_TYPES, DOCUMENT_TYPES

from config import DATABASE_URI, DATABASE_NAME, COLLECTION_NAME, USE_CAPTION_FILTER

logger = logging.getLogger(__name__)

# ── Motor client ──────────────────────────────────────────────────────────────
_client    = AsyncIOMotorClient(DATABASE_URI)
_db        = _client[DATABASE_NAME]
_col       = _db[COLLECTION_NAME]
_users_col = _db["users"]          # ← separate collection for user registry


# ─────────────────────────────────────────────────────────────────────────────
#  User registry
# ─────────────────────────────────────────────────────────────────────────────

class Users:
    """Save and query bot users for broadcast."""

    collection = _users_col

    @classmethod
    async def ensure_indexes(cls):
        await _users_col.create_index([("user_id", ASCENDING)], unique=True, background=True)

    @classmethod
    async def add(cls, user) -> bool:
        """
        Upsert a Pyrogram User object.
        Returns True if newly inserted, False if already existed (just updated).
        """
        from datetime import datetime, timezone
        doc = {
            "user_id":    user.id,
            "first_name": user.first_name or "",
            "last_name":  user.last_name  or "",
            "username":   user.username   or "",
            "is_bot":     user.is_bot,
            "last_seen":  datetime.now(timezone.utc),
        }
        result = await _users_col.update_one(
            {"user_id": user.id},
            {"$set": doc, "$setOnInsert": {"joined": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return result.upserted_id is not None   # True = new user

    @classmethod
    async def get_all_ids(cls) -> list[int]:
        """Return list of all saved user_ids."""
        cursor = _users_col.find({}, {"user_id": 1, "_id": 0})
        docs   = await cursor.to_list(length=None)
        return [d["user_id"] for d in docs]

    @classmethod
    async def count(cls) -> int:
        return await _users_col.count_documents({})

    @classmethod
    async def remove(cls, user_id: int):
        """Remove a user (e.g. they blocked the bot)."""
        await _users_col.delete_one({"user_id": user_id})


# ─────────────────────────────────────────────────────────────────────────────
#  File-ID helpers (ported from original helpers.py)
# ─────────────────────────────────────────────────────────────────────────────

def _encode_file_id(s: bytes) -> str:
    r, n = b"", 0
    for i in s + bytes([22]) + bytes([4]):
        if i == 0:
            n += 1
        else:
            if n:
                r += b"\x00" + bytes([n])
                n = 0
            r += bytes([i])
    return base64.urlsafe_b64encode(r).decode().rstrip("=")


def _encode_file_ref(file_ref: bytes) -> str:
    return base64.urlsafe_b64encode(file_ref).decode().rstrip("=")


def unpack_new_file_id(new_file_id: str):
    """Return (file_id, file_ref) as compact base64 strings."""
    decoded = FileId.decode(new_file_id)
    file_id = _encode_file_id(
        pack(
            "<iiqq",
            int(decoded.file_type),
            decoded.dc_id,
            decoded.media_id,
            decoded.access_hash,
        )
    )
    file_ref = _encode_file_ref(decoded.file_reference)
    return file_id, file_ref


# ─────────────────────────────────────────────────────────────────────────────
#  Media "model" – thin wrapper around the collection
# ─────────────────────────────────────────────────────────────────────────────

class Media:
    """Thin interface to the files collection."""

    collection = _col  # expose for admin commands that need raw access

    # ── Index creation ────────────────────────────────────────────────────────
    @classmethod
    async def ensure_indexes(cls):
        """Create indexes on first run (idempotent)."""
        await _col.create_index([("file_name", TEXT)], background=True)
        await _col.create_index([("file_id", ASCENDING)], unique=True, background=True)
        await Users.ensure_indexes()
        logger.info("DB indexes ensured.")

    # ── CRUD ──────────────────────────────────────────────────────────────────
    @classmethod
    async def save(cls, doc: dict) -> bool:
        """
        Insert a document.  Returns True if saved, False if duplicate.
        """
        try:
            await _col.insert_one(doc)
            logger.info("Saved: %s", doc.get("file_name"))
            return True
        except DuplicateKeyError:
            logger.debug("Duplicate (skipped): %s", doc.get("file_name"))
            return False

    @classmethod
    async def count_documents(cls, filter: dict = None) -> int:
        return await _col.count_documents(filter or {})

    @classmethod
    async def search(
        cls,
        query: str,
        file_type: str = None,
        max_results: int = 10,
        offset: int = 0,
    ):
        """
        Return (files_list, next_offset_or_empty_string).

        files_list entries are plain dicts with keys:
            file_id, file_ref, file_name, file_size, file_type,
            mime_type, caption
        """
        query = query.strip()

        # Build regex pattern
        if not query:
            raw_pattern = "."
        elif " " not in query:
            raw_pattern = r"(\b|[\.+\-_])" + re.escape(query) + r"(\b|[\.+\-_])"
        else:
            raw_pattern = re.escape(query).replace(r"\ ", r".*[\s\.+\-_()\[\]]")

        try:
            regex = re.compile(raw_pattern, flags=re.IGNORECASE)
        except re.error:
            return [], ""

        filt: dict = (
            {"$or": [{"file_name": regex}, {"caption": regex}]}
            if USE_CAPTION_FILTER
            else {"file_name": regex}
        )

        if file_type:
            filt["file_type"] = file_type

        total = await _col.count_documents(filt)
        next_offset = offset + max_results
        if next_offset >= total:
            next_offset = ""

        cursor = (
            _col.find(filt)
            .sort("$natural", DESCENDING)
            .skip(offset)
            .limit(max_results)
        )

        files = await cursor.to_list(length=max_results)
        return files, next_offset

    @classmethod
    async def delete_one(cls, filt: dict):
        return await _col.delete_one(filt)


# ─────────────────────────────────────────────────────────────────────────────
#  Public helpers (used by plugins)
# ─────────────────────────────────────────────────────────────────────────────

async def save_file(media) -> bool:
    """
    Accept a Pyrogram media object (document / video / audio),
    unpack its file_id and persist to MongoDB.
    """
    try:
        file_id, file_ref = unpack_new_file_id(media.file_id)
    except Exception:
        logger.exception("Could not unpack file_id for %s", getattr(media, "file_name", "?"))
        return False

    doc = {
        "_id":       file_id,
        "file_id":   file_id,
        "file_ref":  file_ref,
        "file_name": media.file_name or "Unknown",
        "file_size": media.file_size or 0,
        "file_type": getattr(media, "file_type", None),
        "mime_type": getattr(media, "mime_type", None),
        "caption":   media.caption.html if getattr(media, "caption", None) else None,
    }
    return await Media.save(doc)


async def get_search_results(query, file_type=None, max_results=10, offset=0):
    """Thin wrapper kept for backward-compat with inline plugin."""
    return await Media.search(query, file_type=file_type,
                              max_results=max_results, offset=offset)


async def delete_file(filt: dict):
    return await Media.delete_one(filt)


# make Users importable from database.db directly
__all__ = ["Media", "Users", "save_file", "get_search_results", "delete_file",
           "_col", "_users_col"]
