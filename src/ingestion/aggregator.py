import logging
from src.ingestion.newsapi_client import NewsAPIClient
from src.ingestion.gnews_client import GNewsClient
# from src.ingestion.mediastack_client import MediastackClient
from src.ingestion.currents_client import CurrentsClient
# from src.ingestion.nytimes_client import NYTimesClient

# from src.ingestion.rss.rss_client import RSSClient

logger=logging.getLogger(__name__)

class NewsAggregator:

    def fetch_all(self):

        articles = []

        newsapi_articles = NewsAPIClient().fetch_top_headlines() or []
        logger.info(f"NewsAPI: {len(newsapi_articles)} articles")
        articles.extend(newsapi_articles)

        gnews_articles = GNewsClient().fetch_articles() or []
        logger.info(f"GNews: {len(gnews_articles)} articles")
        articles.extend(gnews_articles)

        currents_articles = CurrentsClient().fetch_articles() or []
        logger.info(f"Currents: {len(currents_articles)} articles")
        articles.extend(currents_articles)


        # rss_articles = RSSClient().fetch_articles() or []
        # logger.info(f"RSS Sources: {len(rss_articles)} articles")
        # articles.extend(rss_articles)


        # mediastack_articles = MediastackClient().fetch_articles() or []
        # logger.info(f"Mediastack: {len(mediastack_articles)} articles")
        # articles.extend(mediastack_articles)


        # nytimes_articles = NYTimesClient().fetch_articles() or []
        # logger.info(f"NYTimes: {len(nytimes_articles)} articles")
        # articles.extend(nytimes_articles)


        logger.info(f"Total Aggregated Articles: {len(articles)}")


        return articles