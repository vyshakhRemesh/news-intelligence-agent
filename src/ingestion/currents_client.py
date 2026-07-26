import requests
from datetime import datetime
from src.config import Config

class CurrentsClient:
    BASE_URL = "https://api.currentsapi.services/v1/latest-news"

    def fetch_articles(self):
        if not Config.CURRENTS_API_KEY:
            return []

        try:
            response = requests.get(
                self.BASE_URL,
                headers={"Authorization": Config.CURRENTS_API_KEY},
                timeout=10
            )
            response.raise_for_status()
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
                    "published_at": self._parse_date(item.get("published")),
                    "fetched_at": datetime.now()
                })

            return articles

        except Exception as e:
            print(f"Currents Error: {e}")
            return []

    def _parse_date(self, date_str):
        if not date_str:
            return datetime.now()
        try:
            return datetime.strptime(date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return datetime.now()