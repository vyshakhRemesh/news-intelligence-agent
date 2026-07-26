import requests
from datetime import datetime
from src.config import Config

class GNewsClient:
    BASE_URL = "https://gnews.io/api/v4"

    def fetch_articles(self):
        if not Config.GNEWS_API_KEY:
            return []

        try:
            response = requests.get(
                f"{self.BASE_URL}/top-headlines",
                params={"token": Config.GNEWS_API_KEY, "lang": "en", "max": 20},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            articles = []
            for item in data.get("articles", []):
                source_name = item.get("source", {}).get("name", "Unknown") if isinstance(item.get("source"), dict) else "Unknown"

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

            return articles

        except Exception as e:
            print(f"GNews Error: {e}")
            return []

    def _parse_date(self, date_str):
        if not date_str:
            return datetime.now()
        try:
            return datetime.strptime(date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return datetime.now()