import feedparser
from .rss_sources import RSS_FEEDS

class RSSClient:

    def fetch_articles(self):

        articles = []

        for source_name, rss_url in RSS_FEEDS.items():

            feed = feedparser.parse(rss_url)

            if feed.bozo:
                print(f"Failed: {source_name}")
                continue

            for entry in feed.entries:

                articles.append({
                    "title": entry.get("title", ""),
                    "author": entry.get("author", ""),
                    "description": entry.get("summary", ""),
                    "content": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "publishedAt": entry.get("published", ""),
                    "source": {
                        "name": source_name
                    }
                })

        return articles