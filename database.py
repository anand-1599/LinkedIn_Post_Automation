"""MongoDB (Motor) async database utilities for posts collection.

Document structure:
{
  _id: ObjectId,
  title: str,
  content: str,
  created_at: datetime (UTC),
  is_approved: bool,
  source_url: str | None,
  batch_timestamp: datetime (UTC),
  image_url: str | None
}
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from bson import ObjectId

MONGO_URI = (
    os.getenv("MONGODB_URI")
    or os.getenv("MONGO_URI")
    or os.getenv("DATABASE_URL")  # fallback if re-using old env var name
)
if not MONGO_URI:
    raise RuntimeError("MONGODB_URI (or MONGO_URI) environment variable is required")

DB_NAME = os.getenv("MONGODB_DB", "linkedin_automation")
COLLECTION_NAME = os.getenv("MONGODB_COLLECTION", "posts")

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None
_collection: AsyncIOMotorCollection | None = None


def get_client() -> AsyncIOMotorClient:
    global _client, _db, _collection
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=8000)
        _db = _client[DB_NAME]
        _collection = _db[COLLECTION_NAME]
    return _client


def get_collection() -> AsyncIOMotorCollection:
    if _collection is None:
        get_client()
    assert _collection is not None
    return _collection


async def ping() -> bool:
    try:
        client = get_client()
        await client.admin.command("ping")
        return True
    except Exception:
        return False


async def create_posts(posts: List[Dict[str, Any]]) -> List[str]:
    if not posts:
        return []
    for p in posts:
        p.setdefault("created_at", datetime.now(timezone.utc))
        p.setdefault("is_approved", False)
    col = get_collection()
    res = await col.insert_many(posts)
    return [str(_id) for _id in res.inserted_ids]


async def list_posts(filter_type: str = "all") -> List[Dict[str, Any]]:
    col = get_collection()
    query: Dict[str, Any] = {}
    if filter_type == "approved":
        query["is_approved"] = True
    elif filter_type == "pending":
        query["is_approved"] = False
    cursor = col.find(query).sort("created_at", -1)
    docs: List[Dict[str, Any]] = []
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        docs.append(doc)
    return docs


async def get_recent_posts(days: int = 30) -> List[Dict[str, Any]]:
    col = get_collection()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cursor = col.find({"created_at": {"$gte": cutoff}}, {"content": 1})
    docs: List[Dict[str, Any]] = []
    async for doc in cursor:
        docs.append({"content": doc.get("content", "")})
    return docs


async def approve_post(post_id: str) -> bool:
    col = get_collection()
    try:
        oid = ObjectId(post_id)
    except Exception:
        return False
    post = await col.find_one({"_id": oid})
    if not post:
        return False
    batch_ts = post.get("batch_timestamp")
    await col.update_one({"_id": oid}, {"$set": {"is_approved": True}})
    if batch_ts:
        await col.delete_many({
            "batch_timestamp": batch_ts,
            "_id": {"$ne": oid},
            "is_approved": False,
        })
    return True


async def update_post_content(post_id: str, content: str) -> bool:
    col = get_collection()
    try:
        oid = ObjectId(post_id)
    except Exception:
        return False
    res = await col.update_one({"_id": oid}, {"$set": {"content": content}})
    return res.modified_count == 1


async def delete_post(post_id: str) -> bool:
    col = get_collection()
    try:
        oid = ObjectId(post_id)
    except Exception:
        return False
    res = await col.delete_one({"_id": oid})
    return res.deleted_count == 1


async def get_post(post_id: str) -> Optional[Dict[str, Any]]:
    col = get_collection()
    try:
        oid = ObjectId(post_id)
    except Exception:
        return None
    doc = await col.find_one({"_id": oid})
    if not doc:
        return None
    doc["id"] = str(doc.pop("_id"))
    return doc