"""
Custom Redis backend for fastapi-cache2 compatible with redis>=5.0

This replaces the built-in RedisBackend which depends on deprecated aioredis package
"""
from typing import Tuple
from redis.asyncio import Redis
from fastapi_cache.backends import Backend
import inspect
import json
from functools import wraps
from typing import Any, Callable, Awaitable

from fastapi_cache import FastAPICache


def jcache(
    key_template: str,
    *,
    ttl: int = 60,
    namespace: str = "",
):
    """
    example:
        @biz_cache("user:{user_id}", ttl=60)
        async def get_user(user_id: int): ...
    """

    def decorator(func: Callable[..., Awaitable[Any]]):
        if not key_template:
            raise ValueError("jcache requires a key_template")

        sig = inspect.signature(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            key = key_template.format(**bound.arguments)
            if namespace:
                key = f"{namespace}:{key}"

            backend = FastAPICache.get_backend()

            cached = await backend.get(key)
            if cached is not None:
                return json.loads(cached)

            result = await func(*args, **kwargs)

            await backend.set(
                key,
                json.dumps(result),
                expire=ttl,
            )
            return result

        return wrapper

    return decorator


def jcache_evict(
    *key_templates: str,
    namespace: str = "",
):
    """
    example:
        @jcache_evict("user:{user_id}")
        async def update_user(user_id: int): ...

        @biz_cache_evict(
            "workflow:{workflow_id}:summary",
            "workflow:{workflow_id}:graph",
        )
        async def finalize_workflow(workflow_id: str): ...
    """

    if not key_templates:
        raise ValueError("jcache_evict requires at least one key_template")

    def decorator(func: Callable[..., Awaitable[Any]]):
        sig = inspect.signature(func)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()

            result = await func(*args, **kwargs)

            backend = FastAPICache.get_backend()

            for template in key_templates:
                key = template.format(**bound.arguments)
                if namespace:
                    key = f"{namespace}:{key}"
                await backend.delete(key)

            return result

        return wrapper

    return decorator


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
