"""Bounded transport recovery; callers explicitly opt in for idempotent work."""
import asyncio

import httpx


async def db_call(callback, *, attempts=1):
    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(callback)
        except httpx.TransportError:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(0.5 * 2 ** attempt)
