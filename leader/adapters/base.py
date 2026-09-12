"""
Leader – Base adapter interface and connection pooling for all backends
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Optional

import aiohttp

from ..models import Task, TaskResult

logger = logging.getLogger("leader.adapters.base")


class BaseAdapter(ABC):
    """
    Abstract base adapter providing connection pooling, exponential backoff with jitter,
    and standardized health-check probing for all backend integrations.
    """

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.id = self.config.get("id", "unknown")
        self._max_retries = int(self.config.get("max_retries", 2))
        self._base_backoff_s = float(self.config.get("base_backoff_s", 0.5))
        self._timeout_s = float(self.config.get("timeout_s", 120.0))
        self._session: Optional[aiohttp.ClientSession] = None

    async def get_session(self) -> aiohttp.ClientSession:
        """Get or create a pooled aiohttp ClientSession with keep-alive and TCP connection reuse."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=20,
                ttl_dns_cache=300,
                keepalive_timeout=30.0,
            )
            timeout = aiohttp.ClientTimeout(total=self._timeout_s, connect=10.0)
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self._session

    async def close(self) -> None:
        """Gracefully terminate pooled connection sessions."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if this backend is properly configured and available.
        Return False if required credentials/config are missing.
        """
        pass

    @abstractmethod
    async def run(self, task: Task) -> TaskResult:
        """
        Execute a task on this backend.
        Return a TaskResult with success/error info.
        """
        pass

    async def run_with_retry(self, task: Task) -> TaskResult:
        """
        Execute run() with exponential backoff and jitter for transient HTTP errors (429/5xx).
        """
        last_error = ""
        for attempt in range(self._max_retries + 1):
            t0 = time.monotonic()
            try:
                res = await self.run(task)
                if res.success:
                    return res
                last_error = res.error
                # Check for rate limit or transient network error to retry
                if attempt < self._max_retries and any(
                    code in last_error
                    for code in (
                        "429",
                        "500",
                        "502",
                        "503",
                        "504",
                        "RateLimit",
                        "Overloaded",
                        "Timeout",
                    )
                ):
                    jitter = random.uniform(0.1, 0.3)
                    delay = (self._base_backoff_s * (2**attempt)) + jitter
                    logger.warning(
                        "Transient error on backend '%s' (attempt %d/%d): %s. Retrying in %.2fs",
                        self.id,
                        attempt + 1,
                        self._max_retries + 1,
                        last_error,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return res
            except Exception as exc:
                last_error = str(exc)
                if attempt < self._max_retries:
                    jitter = random.uniform(0.1, 0.3)
                    delay = (self._base_backoff_s * (2**attempt)) + jitter
                    await asyncio.sleep(delay)
                    continue
                return TaskResult(
                    task_id=task.task_id,
                    backend_id=self.id,
                    output="",
                    success=False,
                    latency_ms=(time.monotonic() - t0) * 1000,
                    error=f"Exhausted {self._max_retries + 1} attempts: {last_error}",
                )

    async def health_check_async(self) -> bool:
        """
        Asynchronous live connectivity probe.
        Default implementation tests availability and base_url if applicable.
        """
        if not self.is_available():
            return False
        base_url = self.config.get("base_url")
        if base_url:
            try:
                session = await self.get_session()
                async with session.get(
                    base_url.rstrip("/") + "/health",
                    timeout=aiohttp.ClientTimeout(total=3.0),
                ) as resp:
                    return resp.status < 500
            except Exception:
                return False
        return True

    def health_check(self) -> bool:
        """Synchronous health check probe."""
        return self.is_available()
