import requests
from src.config import Config


class GNewsClient:

    BASE_URL = "https://gnews.io/api/v4"

    def fetch_articles(self):

        if not Config.GNEWS_API_KEY:
            return []

        try:
            response = requests.get(
                f"{self.BASE_URL}/top-headlines",
                params={
                    "token": Config.GNEWS_API_KEY,
                    "lang": "en",
                    "max": 20
                }
            )

            response.raise_for_status()

            data = response.json()

            articles = []

            for item in data.get("articles", []):

                articles.append({
                    "title": item.get("title"),
                    "author": item.get("source", {}).get("name"),
                    "source": {
                        "name": "GNews"
                    },
                    "description": item.get("description"),
                    "content": item.get("content"),
                    "url": item.get("url"),
                    "publishedAt": item.get("publishedAt"),
                    "source_type": "API"
                })

            return articles

        except Exception as e:
            print(f"GNews Error: {e}")
            return []