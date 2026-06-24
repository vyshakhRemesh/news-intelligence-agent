from src.ingestion.newsapi_client import NewsAPIClient
from src.ingestion.gnews_client import GNewsClient
from src.ingestion.mediastack_client import MediastackClient
from src.ingestion.currents_client import CurrentsClient
from src.ingestion.nytimes_client import NYTimesClient

from src.ingestion.rss.rss_client import RSSClient


class NewsAggregator:

    def fetch_all(self):

        articles = []

        articles.extend(
            NewsAPIClient().fetch_top_headlines() or []
        )

        articles.extend(
            GNewsClient().fetch_articles() or []
        )

        articles.extend(
            MediastackClient().fetch_articles() or []
        )

        articles.extend(
            CurrentsClient().fetch_articles() or []
        )

        articles.extend(
            NYTimesClient().fetch_articles() or []
        )

        articles.extend(
            RSSClient().fetch_all_feeds() or []
        )

        return articles