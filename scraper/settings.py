"""Конфигурация Scrapy: нагрузка, Playwright, middleware, pipelines."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BOT_NAME = "bankruptscout"
SPIDER_MODULES = ["scraper.spiders"]
NEWSPIDER_MODULE = "scraper.spiders"

ROBOTSTXT_OBEY = os.environ.get("ROBOTSTXT_OBEY", "false").lower() == "true"

DOWNLOAD_DELAY = float(os.environ.get("DOWNLOAD_DELAY", "2.0"))
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS = int(os.environ.get("CONCURRENT_REQUESTS", "2"))
CONCURRENT_REQUESTS_PER_DOMAIN = int(os.environ.get("CONCURRENT_REQUESTS_PER_DOMAIN", "1"))

AUTOTHROTTLE_ENABLED = os.environ.get("AUTOTHROTTLE_ENABLED", "true").lower() == "true"
AUTOTHROTTLE_START_DELAY = float(os.environ.get("AUTOTHROTTLE_START_DELAY", "2.0"))
AUTOTHROTTLE_MAX_DELAY = float(os.environ.get("AUTOTHROTTLE_MAX_DELAY", "30.0"))
AUTOTHROTTLE_TARGET_CONCURRENCY = float(os.environ.get("AUTOTHROTTLE_TARGET_CONCURRENCY", "0.5"))

RETRY_ENABLED = True
RETRY_TIMES = int(os.environ.get("RETRY_TIMES", "5"))
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
RETRY_BACKOFF_BASE = float(os.environ.get("RETRY_BACKOFF_BASE", "2.0"))

JOBDIR = os.environ.get("SCRAPY_JOBDIR") or None

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = os.environ.get("PLAYWRIGHT_BROWSER_TYPE", "chromium")
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
}
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = int(
    os.environ.get("PLAYWRIGHT_NAV_TIMEOUT_MS", "120000")
)

BROWSER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

DEFAULT_REQUEST_HEADERS = {
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

DOWNLOADER_MIDDLEWARES = {
    "scraper.middlewares.HttpProxyMiddleware": 350,
    "scraper.middlewares.UserAgentRotator": 400,
    "scraper.middlewares.BackoffRetryMiddleware": 550,
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
}

ITEM_PIPELINES = {
    "scraper.pipelines.StoragePipeline": 300,
}

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATEFORMAT = "%Y-%m-%d %H:%M:%S"
