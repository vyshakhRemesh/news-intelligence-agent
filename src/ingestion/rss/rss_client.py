import feedparser
from datetime import datetime
from .rss_sources import RSS_FEEDS

class RSSClient:
    def fetch_articles(self):
        articles = []
        for source_name, rss_url in RSS_FEEDS.items():
            feed = feedparser.parse(rss_url)
            if feed.bozo:
                print(f"RSS Failed: {source_name}")
                continue

            for entry in feed.entries:
                published = entry.get("published", entry.get("updated", ""))
                published_at = self._parse_date(published)

                articles.append({
                    "title": entry.get("title", ""),
                    "author": entry.get("author", ""),
                    "source_name": source_name,
                    "source_type": "RSS",
                    "description": entry.get("summary", ""),
                    "content": entry.get("summary", ""),
                    "url": entry.get("link", ""),
                    "published_at": published_at,
                    "fetched_at": datetime.now()
                })

        return articles

    def _parse_date(self, date_str):
        if not date_str:
            return datetime.now()
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return datetime.now()