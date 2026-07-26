import logging
import time
from datetime import datetime
from src.ingestion.newsapi_client import NewsAPIClient
from src.ingestion.gnews_client import GNewsClient
from src.ingestion.currents_client import CurrentsClient
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
    # Registry: name → (client_class, method_name)
    API_SOURCES = {
        "newsapi": (NewsAPIClient, "fetch_top_headlines"),
        "gnews": (GNewsClient, "fetch_articles"),
        "currents": (CurrentsClient, "fetch_articles"),
    }

    def __init__(self):
        self.breakers = {
            name: CircuitBreaker(name)
            for name in list(self.API_SOURCES.keys()) + ["rss"]
        }

    def fetch_all(self):
        all_articles = []

        # Fetch API sources
        for name, (client_class, method_name) in self.API_SOURCES.items():
            breaker = self.breakers[name]
            client = client_class()
            fetch_method = getattr(client, method_name)
            articles = breaker.call(fetch_method)
            all_articles.extend(articles)
            logger.info(f"{name}: {len(articles)} articles")

        # Fetch RSS
        rss_breaker = self.breakers["rss"]
        rss_articles = rss_breaker.call(RSSClient().fetch_articles)
        all_articles.extend(rss_articles)
        logger.info(f"RSS: {len(rss_articles)} articles")

        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles

    def add_source(self, name, client_class, method_name="fetch_articles"):
        """Dynamically add a new API source"""
        self.API_SOURCES[name] = (client_class, method_name)
        self.breakers[name] = CircuitBreaker(name)
        logger.info(f"Added source: {name}")