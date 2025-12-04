"""
Custom Redis backend for fastapi-cache2 compatible with redis>=5.0

This replaces the built-in RedisBackend which depends on deprecated aioredis package
"""
from typing import Tuple
from redis.asyncio import Redis
from fastapi_cache.backends import Backend


class RedisBackend(Backend):
    """Redis backend using redis.asyncio (compatible with Python 3.11+)"""

    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_with_ttl(self, key: str) -> Tuple[int, str]:
        """Get value and TTL in a single pipeline operation"""
        async with self.redis.pipeline(transaction=True) as pipe:
            return await (pipe.ttl(key).get(key).execute())

    async def get(self, key: str) -> str:
        """Get cached value by key"""
        return await self.redis.get(key)

    async def set(self, key: str, value: str, expire: int = None):
        """Set cached value with optional expiration"""
        return await self.redis.set(key, value, ex=expire)

    async def clear(self, namespace: str = None, key: str = None) -> int:
        """Clear cache by namespace or specific key"""
        if namespace:
            lua = f"for i, name in ipairs(redis.call('KEYS', '{namespace}:*')) do redis.call('DEL', name); end"
            return await self.redis.eval(lua, numkeys=0)
        elif key:
            return await self.redis.delete(key)
