import logging
from datetime import datetime
from typing import List, Dict, Any

from src.ingestion.base_client import BaseNewsClient
from src.config import Config

logger = logging.getLogger(__name__)


class GNewsClient(BaseNewsClient):
    """GNews.io client with retry, session pooling, and robust date parsing."""

    BASE_URL = "https://gnews.io/api/v4"

    def __init__(self):
        super().__init__(timeout=10)

    def fetch_articles(self) -> List[Dict[str, Any]]:
        """Fetch articles from GNews."""
        if not Config.GNEWS_API_KEY:
            logger.warning("GNews API key not configured")
            return []

        try:
            response = self._get(
                f"{self.BASE_URL}/top-headlines",
                params={
                    "token": Config.GNEWS_API_KEY,
                    "lang": "en",
                    "max": 20,
                },
            )
            data = response.json()

            articles = []
            for item in data.get("articles", []):
                source_name = (
                    item.get("source", {}).get("name", "Unknown")
                    if isinstance(item.get("source"), dict)
                    else "Unknown"
                )

                articles.append({
                    "title": item.get("title", ""),
                    "author": item.get("author", ""),
                    "source_name": source_name,
                    "source_type": "API",
                    "description": item.get("description", ""),
                    "content": item.get("content", ""),
                    "url": item.get("url", ""),
                    "published_at": self._parse_iso_date(item.get("publishedAt")),
                    "fetched_at": datetime.now(),
                })

            logger.info("GNews: %d articles", len(articles))
            return articles

        except Exception as exc:
            logger.error("GNews fetch failed: %s", exc)
            return []
