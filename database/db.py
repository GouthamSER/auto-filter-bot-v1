"""
database/db.py  –  All MongoDB interactions for MediaSearchBot

Dual-DB support
───────────────
• DB1 (DATABASE_URI)   — always active; primary/legacy database
• DB2 (DATABASE_URI_2) — optional second database

Write behaviour:
  new files  → saved to DB2 if set, otherwise DB1
  new users  → saved to DB2 if set, otherwise DB1

Read / Search behaviour:
  1. Query DB2 first (if set)
  2. If DB2 returns results → return them
  3. If DB2 empty → fall back and query DB1
  This means the bot always serves results regardless of which DB
  the file was originally indexed into.

Count behaviour (for /total, status page):
  Returns DB1 + DB2 combined total.
"""

import re
import logging
import base64
from struct import pack

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import TEXT, ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from pyrogram.file_id import FileId

from config import (
    DATABASE_URI,  DATABASE_NAME,  COLLECTION_NAME,
    DATABASE_URI_2, DATABASE_NAME_2, COLLECTION_NAME_2,
    USE_CAPTION_FILTER,
)

logger = logging.getLogger(__name__)

# ── DB1 (primary / always active) ─────────────────────────────────────────────
_client1   = AsyncIOMotorClient(DATABASE_URI)
_db1       = _client1[DATABASE_NAME]
_col1      = _db1[COLLECTION_NAME]
_users_col1 = _db1["users"]

# ── DB2 (secondary / optional) ────────────────────────────────────────────────
_DUAL = bool(DATABASE_URI_2)

if _DUAL:
    _client2    = AsyncIOMotorClient(DATABASE_URI_2)
    _db2        = _client2[DATABASE_NAME_2]
    _col2       = _db2[COLLECTION_NAME_2]
    _users_col2 = _db2["users"]
    logger.info("Dual-DB mode active — writes → DB2, reads → DB2 then DB1")
else:
    _col2       = None
    _users_col2 = None
    logger.info("Single-DB mode — using DB1 only")

# ── Convenience references used by plugins that import _col directly ──────────
# Search.py imports _col for _count(); point it at DB2 when dual mode is on
# so counts match the active write target.  Falls back to _col1 when single.
_col       = _col2 if _DUAL else _col1
_users_col = _users_col2 if _DUAL else _users_col1


# ─────────────────────────────────────────────────────────────────────────────
#  File-ID helpers
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
#  Internal search helper
# ─────────────────────────────────────────────────────────────────────────────

def _build_regex(query: str):
    query = query.strip()
    if not query:
        raw = "."
    elif " " not in query:
        raw = r"(\b|[\.+\-_])" + re.escape(query) + r"(\b|[\.+\-_])"
    else:
        raw = re.escape(query).replace(r"\ ", r".*[\s\.+\-_()\[\]]")
    return re.compile(raw, flags=re.IGNORECASE)


def _build_filter(regex, file_type: str = None) -> dict:
    filt: dict = (
        {"$or": [{"file_name": regex}, {"caption": regex}]}
        if USE_CAPTION_FILTER
        else {"file_name": regex}
    )
    if file_type:
        filt["file_type"] = file_type
    return filt


async def _search_col(col, filt: dict, max_results: int, offset: int):
    """Run a search against one collection. Returns (files, total)."""
    total  = await col.count_documents(filt)
    cursor = (
        col.find(filt)
        .sort("$natural", DESCENDING)
        .skip(offset)
        .limit(max_results)
    )
    files = await cursor.to_list(length=max_results)
    return files, total


# ─────────────────────────────────────────────────────────────────────────────
#  Users
# ─────────────────────────────────────────────────────────────────────────────

class Users:
    """Save and query bot users for broadcast.

    In dual-DB mode users are stored in DB2 (write target).
    In single-DB mode users are stored in DB1.
    Reads always come from the active write target (_users_col).
    """

    @classmethod
    async def ensure_indexes(cls):
        await _users_col1.create_index([("user_id", ASCENDING)], unique=True, background=True)
        if _DUAL:
            await _users_col2.create_index([("user_id", ASCENDING)], unique=True, background=True)

    @classmethod
    async def add(cls, user) -> bool:
        """
        Upsert a Pyrogram User object into the active write target.
        Returns True if newly inserted.
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
        target = _users_col2 if _DUAL else _users_col1
        result = await target.update_one(
            {"user_id": user.id},
            {"$set": doc, "$setOnInsert": {"joined": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return result.upserted_id is not None

    @classmethod
    async def get_all_ids(cls) -> list[int]:
        """Return all user_ids from the active write target."""
        target = _users_col2 if _DUAL else _users_col1
        cursor = target.find({}, {"user_id": 1, "_id": 0})
        docs   = await cursor.to_list(length=None)
        return [d["user_id"] for d in docs]

    @classmethod
    async def count(cls) -> int:
        """Count users in the active write target."""
        target = _users_col2 if _DUAL else _users_col1
        return await target.count_documents({})

    @classmethod
    async def remove(cls, user_id: int):
        """Remove a user from the active write target."""
        target = _users_col2 if _DUAL else _users_col1
        await target.delete_one({"user_id": user_id})


# ─────────────────────────────────────────────────────────────────────────────
#  Media
# ─────────────────────────────────────────────────────────────────────────────

class Media:
    """Thin interface to the files collection(s).

    Writes always go to the active write target (DB2 if dual, else DB1).
    Searches hit DB2 first, fall back to DB1 if no results found.
    """

    # expose for admin commands that do raw collection access
    collection = _col2 if _DUAL else _col1

    @classmethod
    async def ensure_indexes(cls):
        """Create indexes on first run (idempotent)."""
        for col in filter(None, [_col1, _col2]):
            await col.create_index([("file_name", TEXT)], background=True)
            await col.create_index([("file_id", ASCENDING)], unique=True, background=True)
        await Users.ensure_indexes()
        mode = "dual-DB" if _DUAL else "single-DB"
        logger.info("DB indexes ensured (%s).", mode)

    @classmethod
    async def save(cls, doc: dict) -> bool:
        """
        Insert into the active write target (DB2 if dual, else DB1).
        Returns True if saved, False if duplicate.
        """
        target = _col2 if _DUAL else _col1
        try:
            await target.insert_one(doc)
            logger.info("Saved: %s", doc.get("file_name"))
            return True
        except DuplicateKeyError:
            logger.debug("Duplicate (skipped): %s", doc.get("file_name"))
            return False

    @classmethod
    async def count_documents(cls, filter: dict = None) -> int:
        """Combined count across both DBs (deduplication not applied)."""
        filt  = filter or {}
        count = await _col1.count_documents(filt)
        if _DUAL:
            count += await _col2.count_documents(filt)
        return count

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

        Dual-DB search strategy:
          1. Query DB2 → if results found, return them
          2. If DB2 empty (or single-DB mode) → query DB1
        This means users who searched before DB2 existed still get results.
        """
        try:
            regex = _build_regex(query)
        except re.error:
            return [], ""

        filt = _build_filter(regex, file_type)

        # ── Dual-DB: try DB2 first ────────────────────────────────────────────
        if _DUAL:
            files2, total2 = await _search_col(_col2, filt, max_results, offset)
            if files2:
                next_offset = offset + max_results
                if next_offset >= total2:
                    next_offset = ""
                return files2, next_offset

        # ── Single-DB or DB2 miss: query DB1 ─────────────────────────────────
        files1, total1 = await _search_col(_col1, filt, max_results, offset)
        next_offset = offset + max_results
        if next_offset >= total1:
            next_offset = ""
        return files1, next_offset

    @classmethod
    async def delete_one(cls, filt: dict):
        """Delete from both DBs so a file can't resurface from the other."""
        r1 = await _col1.delete_one(filt)
        if _DUAL:
            await _col2.delete_one(filt)
        return r1


# ─────────────────────────────────────────────────────────────────────────────
#  Public helpers (used by plugins)
# ─────────────────────────────────────────────────────────────────────────────

async def save_file(media) -> bool:
    """
    Accept a Pyrogram media object (document / video / audio),
    unpack its file_id and persist to the active write target.
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


# dual-DB flag exposed so plugins can show DB status
DUAL_DB = _DUAL

__all__ = [
    "Media", "Users", "save_file", "get_search_results", "delete_file",
    "_col", "_col1", "_col2", "_users_col", "DUAL_DB",
    "unpack_new_file_id",
]
