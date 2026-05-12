from __future__ import annotations

import logging
import time
from collections.abc import Callable
from email.utils import parsedate_to_datetime

import httpx

from nba_data.config.settings import Settings
from nba_data.scraping.cache import HtmlCache

logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    """Raised when the remote site keeps responding with rate-limit errors."""


class BasketballReferenceClient:
    """Central sync HTTP client for Basketball Reference requests."""

    def __init__(
        self,
        settings: Settings,
        cache: HtmlCache | None = None,
        *,
        http_client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        max_429_retries: int = 1,
        max_5xx_retries: int = 2,
    ) -> None:
        self.settings = settings
        self.cache = cache
        self._client = http_client or httpx.Client(
            timeout=settings.scraper_timeout_seconds,
            headers={"User-Agent": settings.scraper_user_agent},
            follow_redirects=True,
        )
        self._owns_client = http_client is None
        self._sleeper = sleeper
        self._clock = clock
        self._last_request_at: float | None = None
        self._max_429_retries = max_429_retries
        self._max_5xx_retries = max_5xx_retries

        if not settings.scraper_user_agent.strip():
            msg = "A non-empty scraper user agent is required"
            raise ValueError(msg)

        if settings.scraper_max_requests_per_minute > 20:
            msg = "Basketball Reference requests must never exceed 20 per minute"
            raise ValueError(msg)

    def get(self, url: str, *, force_refresh: bool = False) -> str:
        should_force = force_refresh or self.settings.scraper_force_refresh
        if self.cache is not None and not should_force:
            cached = self.cache.get(url)
            if cached is not None:
                logger.info("HTML cache hit for %s", url)
                return cached

        html = self._get_from_network(url)
        if self.cache is not None:
            self.cache.set(url, html)
        return html

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> BasketballReferenceClient:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _get_from_network(self, url: str) -> str:
        too_many_requests = 0
        server_errors = 0

        while True:
            self._wait_for_rate_limit()
            logger.info("Requesting %s", url)
            response = self._client.get(url, headers={"User-Agent": self.settings.scraper_user_agent})
            self._last_request_at = self._clock()

            if response.status_code == 429:
                too_many_requests += 1
                retry_after = self._retry_after_seconds(response)
                logger.warning("HTTP 429 for %s; retry_after=%s", url, retry_after)
                if too_many_requests > self._max_429_retries:
                    msg = f"Repeated HTTP 429 while requesting {url}; stop the scraping job"
                    raise RateLimitExceededError(msg)
                self._sleeper(max(retry_after, 60.0))
                continue

            if 500 <= response.status_code < 600 and server_errors < self._max_5xx_retries:
                server_errors += 1
                self._sleeper(2.0 * server_errors)
                continue

            response.raise_for_status()
            return response.text

    def _wait_for_rate_limit(self) -> None:
        if self._last_request_at is None:
            return
        rpm_delay = 60.0 / min(self.settings.scraper_max_requests_per_minute, 20)
        required_delay = max(self.settings.scraper_min_delay_seconds, rpm_delay)
        elapsed = self._clock() - self._last_request_at
        if elapsed < required_delay:
            self._sleeper(required_delay - elapsed)

    def _retry_after_seconds(self, response: httpx.Response) -> float:
        value = response.headers.get("Retry-After")
        if value is None:
            return 60.0

        try:
            return max(float(value), 0.0)
        except ValueError:
            pass

        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return 60.0

        return max(retry_at.timestamp() - time.time(), 0.0)
