import logging
from datetime import datetime
from typing import List, Dict, Any

from src.ingestion.base_client import BaseNewsClient
from src.config import Config

logger = logging.getLogger(__name__)


class CurrentsClient(BaseNewsClient):
    """CurrentsAPI client with retry, session pooling, and robust date parsing."""

    BASE_URL = "https://api.currentsapi.services/v1/latest-news"

    def __init__(self):
        super().__init__(timeout=10)

    def fetch_articles(self) -> List[Dict[str, Any]]:
        """Fetch articles from CurrentsAPI."""
        if not Config.CURRENTS_API_KEY:
            logger.warning("Currents API key not configured")
            return []

        try:
            response = self._get(
                self.BASE_URL,
                headers={"Authorization": Config.CURRENTS_API_KEY},
            )
            data = response.json()

            articles = []
            for item in data.get("news", []):
                source_name = item.get("author") or "Currents"

                articles.append({
                    "title": item.get("title", ""),
                    "author": item.get("author", ""),
                    "source_name": source_name,
                    "source_type": "API",
                    "description": item.get("description", ""),
                    "content": item.get("description", ""),
                    "url": item.get("url", ""),
                    "published_at": self._parse_iso_date(item.get("published")),
                    "fetched_at": datetime.now(),
                })

            logger.info("Currents: %d articles", len(articles))
            return articles

        except Exception as exc:
            logger.error("Currents fetch failed: %s", exc)
            return []
