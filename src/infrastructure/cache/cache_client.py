import os
import json
from typing import Any, Optional, Protocol

class CacheClient(Protocol):
    async def get(self, key: str) -> Optional[Any]:
        ...
        
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ...
        
    async def delete(self, key: str) -> None:
        ...


class InMemoryCache:
    """
    A simple in-memory cache for local development.
    In a real environment, this should be replaced by a Redis client.
    """
    def __init__(self):
        self._store = {}
        
    async def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)
        
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        # Note: TTL is ignored in this simple mock
        self._store[key] = value
        
    async def delete(self, key: str) -> None:
        if key in self._store:
            del self._store[key]


# In a real app, you would conditionally initialize RedisCache here based on config.
# REDIS_URL = os.getenv("REDIS_URL")
# if REDIS_URL:
#     cache: CacheClient = RedisCache(REDIS_URL)
# else:
cache: CacheClient = InMemoryCache()
