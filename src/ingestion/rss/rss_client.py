# import feedparser
# from .rss_sources import RSS_FEEDS

# class RSSClient:

#     def fetch_articles(self):

#         articles = []

#         for rss_url in RSS_FEEDS:

#             feed = feedparser.parse(rss_url)

#             for entry in feed.entries:

#                 articles.append({
#                     "title": entry.get("title"),
#                     "author": entry.get("author"),
#                     "description": entry.get("summary"),
#                     "content": entry.get("summary"),
#                     "url": entry.get("link"),
#                     "publishedAt": entry.get("published"),
#                     "source": {
#                         "name": feed.feed.get("title")
#                     }
#                 })

#         return articles




# cross check if the rss integration is correct