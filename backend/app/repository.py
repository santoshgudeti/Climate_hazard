"""Caching repository. MongoDB is optional locally; both paths use the same keys."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
from pymongo import MongoClient, ASCENDING
from .config import MONGODB_URI, MONGODB_DATABASE, WEATHER_CACHE_TTL_SECONDS, ANALYSIS_CACHE_TTL_SECONDS


class CacheRepository:
    def __init__(self) -> None:
        self.memory: dict[str, dict[str, Any]] = {}
        self.client = None
        self.db = None
        if MONGODB_URI:
            self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=2500)
            self.db = self.client[MONGODB_DATABASE]
            self.db.weather_cache.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
            self.db.analysis_cache.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        if self.db is not None:
            document = self.db[collection].find_one({"key": key, "expires_at": {"$gt": now}}, {"_id": 0})
            return document.get("payload") if document else None
        document = self.memory.get(f"{collection}:{key}")
        return document["payload"] if document and document["expires_at"] > now else None

    def set(self, collection: str, key: str, payload: dict[str, Any]) -> None:
        ttl = WEATHER_CACHE_TTL_SECONDS if collection == "weather_cache" else ANALYSIS_CACHE_TTL_SECONDS
        now = datetime.now(timezone.utc)
        document = {"key": key, "payload": payload, "created_at": now, "expires_at": now + timedelta(seconds=ttl)}
        if self.db is not None:
            self.db[collection].replace_one({"key": key}, document, upsert=True)
        else:
            self.memory[f"{collection}:{key}"] = document
