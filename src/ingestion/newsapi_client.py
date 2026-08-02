import requests
import logging
from datetime import datetime
from src.config import Config

logger = logging.getLogger(__name__)

class NewsAPIClient:
    BASE_URL = "https://newsapi.org/v2"

    def __init__(self):
        self.api_key = Config.NEWS_API_KEY
        self.headers = {"X-Api-Key": self.api_key}

    def fetch_top_headlines(self, category="general", language="en", page_size=100):
        endpoint = f"{self.BASE_URL}/top-headlines"
        params = {
            "category": category,
            "language": language,
            "pageSize": page_size
        }

        try:
            logger.info(f"Fetching NewsAPI: {category}")
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "ok":
                logger.error(f"NewsAPI error: {data.get('message')}")
                return []

            articles = []
            for item in data.get("articles", []):
                source_obj = item.get("source", {})
                source_name = source_obj.get("name", "NewsAPI") if isinstance(source_obj, dict) else "NewsAPI"

                articles.append({
                    "title": item.get("title", ""),
                    "author": item.get("author", ""),
                    "source_name": source_name,
                    "source_type": "API",
                    "description": item.get("description", ""),
                    "content": item.get("content", ""),
                    "url": item.get("url", ""),
                    "published_at": self._parse_date(item.get("publishedAt")),
                    "fetched_at": datetime.now()
                })

            logger.info(f"NewsAPI: {len(articles)} articles")
            return articles

        except requests.exceptions.RequestException as e:
            logger.error(f"NewsAPI network error: {e}")
            return []  # FIX: was returning None, which breaks all_articles.extend()

    def _parse_date(self, date_str):
        if not date_str:
            return datetime.now()
        try:
            return datetime.strptime(date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return datetime.now()
