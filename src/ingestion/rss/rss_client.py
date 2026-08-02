import feedparser
import logging
from datetime import datetime
from .rss_sources import RSS_FEEDS

logger = logging.getLogger(__name__)


class RSSClient:
    def fetch_articles(self):
        articles = []
        for source_name, rss_url in RSS_FEEDS.items():
            try:
                feed = feedparser.parse(rss_url)

                # FIX: Do NOT skip based on bozo bit alone.
                # Many valid feeds set bozo for minor XML warnings.
                # Only skip if we actually got zero entries.
                if not feed.entries:
                    logger.warning(f"RSS: No entries from {source_name}")
                    continue

                if feed.bozo:
                    logger.debug(f"RSS: {source_name} has bozo bit but {len(feed.entries)} entries — processing anyway")

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

                logger.info(f"RSS {source_name}: {len(feed.entries)} entries")

            except Exception as exc:
                logger.error(f"RSS {source_name} failed: {exc}")
                continue

        logger.info(f"RSS total: {len(articles)} articles")
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
