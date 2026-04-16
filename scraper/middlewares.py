"""Middleware: прокси, ротация User-Agent, повторные запросы с задержкой."""

from __future__ import annotations

import logging
import os
import random
import time
from typing import TYPE_CHECKING

from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.http import Request

if TYPE_CHECKING:
    from scrapy.crawler import Crawler

log = logging.getLogger(__name__)


class HttpProxyMiddleware:
    """Устанавливает прокси из переменных окружения HTTP_PROXY / HTTPS_PROXY."""

    def process_request(self, request: Request) -> None:
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
        if proxy_url:
            request.meta["proxy"] = proxy_url


class UserAgentRotator:
    """Случайный User-Agent из настроек BROWSER_AGENTS на каждый запрос."""

    def __init__(self, agents: list[str]) -> None:
        self._agents = agents if agents else [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        ]

    @classmethod
    def from_crawler(cls, crawler: Crawler) -> UserAgentRotator:
        raw = crawler.settings.getlist("BROWSER_AGENTS")
        return cls(list(raw))

    def process_request(self, request: Request) -> None:
        agent = random.choice(self._agents)
        request.headers.setdefault(b"User-Agent", agent.encode())


class BackoffRetryMiddleware(RetryMiddleware):
    """Экспоненциальная пауза перед повторной отправкой неудачного запроса."""

    MAX_SLEEP = 300.0

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._base = settings.getfloat("RETRY_BACKOFF_BASE", 2.0)

    def _retry(self, request: Request, reason, spider):
        attempt = request.meta.get("retry_times", 0) + 1
        wait = min(self._base ** min(attempt, 10), self.MAX_SLEEP)
        log.warning(
            "Попытка %d/%d для %s, пауза %.1f с — причина: %s",
            attempt,
            self.max_retry_times,
            request.url,
            wait,
            reason,
        )
        time.sleep(wait)
        return super()._retry(request, reason, spider)
