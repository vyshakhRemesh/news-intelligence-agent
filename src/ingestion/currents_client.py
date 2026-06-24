import requests
from src.config import Config


class CurrentsClient:

    BASE_URL = "https://api.currentsapi.services/v1/latest-news"

    def fetch_articles(self):

        if not Config.CURRENTS_API_KEY:
            return []

        try:

            response = requests.get(
                self.BASE_URL,
                headers={
                    "Authorization": Config.CURRENTS_API_KEY
                }
            )

            response.raise_for_status()

            data = response.json()

            articles = []

            for item in data.get("news", []):

                articles.append({
                    "title": item.get("title"),
                    "author": item.get("author"),
                    "source": {
                        "name": item.get("author")
                    },
                    "description": item.get("description"),
                    "content": item.get("description"),
                    "url": item.get("url"),
                    "publishedAt": item.get("published"),
                    "source_type": "API"
                })

            return articles

        except Exception as e:
            print(f"Currents Error: {e}")
            return []