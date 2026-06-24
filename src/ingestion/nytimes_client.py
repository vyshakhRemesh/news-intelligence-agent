import requests
from src.config import Config


class NYTimesClient:

    BASE_URL = "https://api.nytimes.com/svc/topstories/v2/home.json"

    def fetch_articles(self):

        if not Config.NYTIMES_API_KEY:
            return []

        try:

            response = requests.get(
                self.BASE_URL,
                params={
                    "api-key": Config.NYTIMES_API_KEY
                }
            )

            response.raise_for_status()

            data = response.json()

            articles = []

            for item in data.get("results", []):

                articles.append({
                    "title": item.get("title"),
                    "author": item.get("byline"),
                    "source": {
                        "name": "New York Times"
                    },
                    "description": item.get("abstract"),
                    "content": item.get("abstract"),
                    "url": item.get("url"),
                    "publishedAt": item.get("published_date"),
                    "source_type": "API"
                })

            return articles

        except Exception as e:
            print(f"NYTimes Error: {e}")
            return []