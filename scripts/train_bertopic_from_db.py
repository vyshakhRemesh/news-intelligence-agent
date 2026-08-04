import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.database.connection import SessionLocal
from src.database.models import RawArticles
from src.topic_modeling.topic_service import TopicService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)


def main():
    db = SessionLocal()

    try:
        logger.info("=" * 60)
        logger.info("BOOTSTRAP BERTopic Training")
        logger.info("=" * 60)

        service = TopicService(db)

        articles = (
            db.query(RawArticles)
            .filter(RawArticles.cleaned_content.isnot(None))
            .filter(RawArticles.is_duplicate == False)
            .all()
        )

        if len(articles) < 10:
            logger.error(
                f"Only {len(articles)} articles found. Need at least 10."
            )
            return

        logger.info(f"Loaded {len(articles)} articles")

        # Force first training
        documents = [a.cleaned_content for a in articles]
        embeddings = service.embedder.generate_embeddings(documents)

        topics, _ = service.topic_model.fit(documents, embeddings)

        topics = service._reassign_outliers(topics, embeddings)

        service.save_topics(articles, topics)

        logger.info("=" * 60)
        logger.info("BERTopic Training Complete")
        logger.info("=" * 60)

    except Exception:
        logger.exception("Training failed")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()