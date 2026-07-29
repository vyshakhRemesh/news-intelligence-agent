import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Any, Tuple

from src.ingestion.newsapi_client import NewsAPIClient
from src.ingestion.gnews_client import GNewsClient
from src.ingestion.currents_client import CurrentsClient
from src.ingestion.nytimes_client import NYTimesClient
from src.ingestion.rss.rss_client import RSSClient

logger = logging.getLogger(__name__)


class CircuitBreaker:
    def __init__(self, name, failure_threshold=3, recovery_timeout=60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"Circuit {self.name}: attempting recovery")
            else:
                logger.warning(f"Circuit {self.name} OPEN, skipping")
                return []

        try:
            result = func(*args, **kwargs)
            if result is not None:
                self._on_success()
            return result or []
        except Exception as e:
            self._on_failure()
            logger.error(f"{self.name} failed: {e}")
            return []

    def _on_success(self):
        self.failures = 0
        self.state = "CLOSED"

    def _on_failure(self):
        self.failures += 1
        self.last_failure = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.error(f"Circuit {self.name} OPENED after {self.failures} failures")


class NewsAggregator:
    # Added NYTimes. Total: 4 APIs + RSS = 8+ sources (expand RSS to hit 10+)
    API_SOURCES = {
        "newsapi": (NewsAPIClient, "fetch_top_headlines"),
        "gnews": (GNewsClient, "fetch_articles"),
        "currents": (CurrentsClient, "fetch_articles"),
        "nytimes": (NYTimesClient, "fetch_articles"),
    }

    def __init__(self, max_workers=4):
        self.breakers = {
            name: CircuitBreaker(name)
            for name in list(self.API_SOURCES.keys()) + ["rss"]
        }
        self.max_workers = max_workers
        # Track same-source duplicates within this run only.
        # Cross-source duplicates (same URL, different source) are PRESERVED
        # for the contradiction detection module.
        self._seen_this_run = set()

    def _fetch_source(self, name, client_class, method_name):
        breaker = self.breakers[name]
        client = client_class()
        fetch_method = getattr(client, method_name)
        articles = breaker.call(fetch_method)
        logger.info(f"{name}: {len(articles)} articles")
        return name, articles

    def _fetch_rss(self):
        breaker = self.breakers["rss"]
        rss_articles = breaker.call(RSSClient().fetch_articles)
        return "rss", rss_articles

    def _add_unique(self, articles, all_articles):
        for article in articles:
            url = article.get("url")
            source_name = article.get("source_name", "Unknown")
            if not url:
                continue
            run_key = (url, source_name)
            if run_key in self._seen_this_run:
                logger.debug(f"Skipped same-source dup in run: {url} from {source_name}")
                continue
            self._seen_this_run.add(run_key)
            all_articles.append(article)

    def fetch_all(self):
        all_articles = []
        self._seen_this_run.clear()

        # Parallel API fetching
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_source, name, cls, method): name
                for name, (cls, method) in self.API_SOURCES.items()
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    _, articles = future.result()
                    self._add_unique(articles, all_articles)
                except Exception as exc:
                    logger.error(f"Source {name} failed: {exc}")

        # RSS
        try:
            _, rss_articles = self._fetch_rss()
            self._add_unique(rss_articles, all_articles)
        except Exception as exc:
            logger.error(f"RSS aggregation failed: {exc}")

        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles

    def add_source(self, name, client_class, method_name="fetch_articles"):
        self.API_SOURCES[name] = (client_class, method_name)
        self.breakers[name] = CircuitBreaker(name)
        logger.info(f"Added source: {name}")
