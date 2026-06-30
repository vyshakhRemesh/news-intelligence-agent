# import requests
# from src.config import Config


# class MediastackClient:

#     BASE_URL = "http://api.mediastack.com/v1/news"

#     def fetch_articles(self):

#         if not Config.MEDIASTACK_API_KEY:
#             return []

#         try:

#             response = requests.get(
#                 self.BASE_URL,
#                 params={
#                     "access_key": Config.MEDIASTACK_API_KEY,
#                     "languages": "en",
#                     "limit": 20
#                 }
#             )

#             response.raise_for_status()

#             data = response.json()

#             articles = []

#             for item in data.get("data", []):

#                 articles.append({
#                     "title": item.get("title"),
#                     "author": item.get("author"),
#                     "source": {
#                         "name": item.get("source")
#                     },
#                     "description": item.get("description"),
#                     "content": item.get("description"),
#                     "url": item.get("url"),
#                     "publishedAt": item.get("published_at"),
#                     "source_type": "API"
#                 })

#             return articles

#         except Exception as e:
#             print(f"Mediastack Error: {e}")
#             return []