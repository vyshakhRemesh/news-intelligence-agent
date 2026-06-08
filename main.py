# main.py
import logging
from datetime import datetime
from src.ingestion.newsapi_client import NewsAPIClient
from src.database.connection import init_db, SessionLocal
from src.database.models import RawArticles

# Configure the global logging layout for our terminal
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_iso_date(date_str: str) -> datetime:
    """
    Helper function to safely parse ISO timestamp strings from the API
    into Python datetime objects. Falls back to current time if parsing fails.
    """
    if not date_str:
        return datetime.utcnow()
    try:
        # NewsAPI returns timestamps formatted as "2026-06-06T03:52:00Z"
        # We strip the trailing 'Z' to make it compatible with standard parsing
        return datetime.strptime(date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.utcnow()

def run_pipeline():
    logger.info("Starting News Intelligence Ingestion Pipeline...")

    # 1. Check database connection and generate tables if they don't exist yet
    init_db()
    
    # 2. Instantiate our API client and fetch top technology headlines
    api_client = NewsAPIClient()
    articles_data = api_client.fetch_top_headlines(category="technology", page_size=20)
    
    # If the network request failed entirely, exit early to protect the database
    if not articles_data:
        logger.warning("No data retrieved from NewsAPI. Terminating pipeline cycle.")
        return

    # 3. Establish a transactional database session context
    db = SessionLocal()
    new_records_count = 0

    try:
        logger.info("Processing articles and filtering for uniqueness...")
        
        for item in articles_data:
            url = item.get("url")
            
            # Skip entries that lack a valid web link
            if not url:
                continue

            # Layer 3 Deduplication Check: Look up the URL in our database
            # If it already exists, skip it entirely to prevent duplicate rows
            exists = db.query(RawArticles).filter(RawArticles.url == url).first()
            if exists:
                continue

            # Construct a brand new database record mapping entity
            article_record = RawArticles(
                title=item.get("title"),
                author=item.get("author"),
                source_name=item.get("source", {}).get("name"),
                description=item.get("description"),
                content=item.get("content"),
                url=url,
                published_at=parse_iso_date(item.get("publishedAt"))
            )
            
            # Stage the record in our active database transaction memory session
            db.add(article_record)
            new_records_count += 1

        # 4. Atomically commit all staged additions to disk if unique entries were found
        if new_records_count > 0:
            db.commit()
            logger.info(f"Pipeline Success! Integrated {new_records_count} fresh articles into PostgreSQL.")
        else:
            logger.info("Pipeline Sync Complete: No new unique articles discovered during this cycle.")

    except Exception as e:
        # If an unhandled database collision or crash happens, wipe the transactional memory
        # to ensure the system doesn't commit broken states.
        db.rollback()
        logger.error(f"Critical error during pipeline transaction execution, rolling back state. Error: {e}")
    finally:
        # Always terminate the connection session to release the port back to the pool
        db.close()

if __name__ == "__main__":
    run_pipeline()