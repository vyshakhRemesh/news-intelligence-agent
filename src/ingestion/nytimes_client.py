import logging
from datetime import datetime
from typing import List, Dict, Any

from src.ingestion.base_client import BaseNewsClient
from src.config import Config

logger = logging.getLogger(__name__)


class NYTimesClient(BaseNewsClient):
    """New York Times API client with retry, session pooling, and robust date parsing."""

    BASE_URL = "https://api.nytimes.com/svc/topstories/v2/home.json"

    def __init__(self):
        super().__init__(timeout=10)

    def fetch_articles(self) -> List[Dict[str, Any]]:
        """Fetch articles from NYTimes Top Stories API."""
        if not Config.NYTIMES_API_KEY:
            logger.warning("NYTimes API key not configured")
            return []

        try:
            response = self._get(
                self.BASE_URL,
                params={"api-key": Config.NYTIMES_API_KEY},
            )
            data = response.json()

            articles = []
            for item in data.get("results", []):
                articles.append({
                    "title": item.get("title", ""),
                    "author": item.get("byline", ""),
                    "source_name": "New York Times",
                    "source_type": "API",
                    "description": item.get("abstract", ""),
                    "content": item.get("abstract", ""),
                    "url": item.get("url", ""),
                    "published_at": self._parse_iso_date(item.get("published_date")),
                    "fetched_at": datetime.now(),
                })

            logger.info("NYTimes: %d articles", len(articles))
            return articles

        except Exception as exc:
            logger.error("NYTimes fetch failed: %s", exc)
            return []
