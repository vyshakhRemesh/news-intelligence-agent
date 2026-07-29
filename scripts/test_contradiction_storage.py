import logging
from datetime import datetime, timezone

from src.database.connection import SessionLocal, init_db
from src.database.models import (
    ArticleContradiction,
    RawArticles,
)
from src.contradiction.contradiction_service import (
    ContradictionService,
)
from src.recommendation.trust_score import TrustScore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_test_article(
    db,
    title: str,
    content: str,
    source_name: str,
    url:str
):
    """
    Insert one fictional article into raw_articles.

    Some fields may need to be adjusted based on the exact
    RawArticles model in your project.
    """

    article = RawArticles(
       title=title,
        author="Contradiction Test",
        source_name=source_name,
        source_type="test",
        description=content,
        content=content,
        cleaned_title=title,
        cleaned_content=content,
        url=url,
        published_at=datetime.now(timezone.utc),
        primary_topic="transport",
        quality_score=90,
        preprocessing_status="completed",
        language="en",

    )

    db.add(article)

    # Sends the INSERT to PostgreSQL and generates article.id,
    # but does not permanently commit yet.
    db.flush()

    return article


def main():
    init_db()
    db = SessionLocal()

    try:
        first_article = create_test_article(
            db=db,
            title=(
                "Riverton council approves public "
                "transport plan"
            ),
            content=(
                "The Riverton City Council approved "
                "the new public transport plan on Monday."
            ),
            source_name="Test News Source A",
            url=(
                "https://test.local/"
                "riverton-transport-approved-1"
            ),
        )

        second_article = create_test_article(
            db=db,
            title=(
                "Riverton council rejects public "
                "transport plan"
            ),
            content=(
                "The Riverton City Council did not approve "
                "the new public transport plan on Monday."
            ),
            source_name="Test News Source B",
            url=(
                "https://test.local/"
                "riverton-transport-rejected-1"
            ),
        )

        db.commit()

        logger.info(
            "Created test articles with IDs %s and %s",
            first_article.id,
            second_article.id,
        )

        from src.recommendation.trust_score import TrustScore


        articles_for_analysis = [
            {
                "article_id": first_article.id,
                "title": first_article.title,
                "source": first_article.source_name,
                "topic": first_article.primary_topic,
                "text": first_article.cleaned_content,
            },
            {
                "article_id": second_article.id,
                "title": second_article.title,
                "source": second_article.source_name,
                "topic": second_article.primary_topic,
                "text": second_article.cleaned_content,
            },
        ]

        for article in articles_for_analysis:
            article["trust_score"] = TrustScore.calculate(article)

        service = ContradictionService(db=db)

        result = service.analyse_against_most_trusted(
            articles=articles_for_analysis,
            threshold=0.50,
            save_results=True,
        )

        logger.info(
            "Contradiction result: %s",
            result,
        )

        stored_rows = (
            db.query(ArticleContradiction)
            .filter(
                ArticleContradiction.article_1_id.in_(
                    [
                        first_article.id,
                        second_article.id,
                    ]
                ),
                ArticleContradiction.article_2_id.in_(
                    [
                        first_article.id,
                        second_article.id,
                    ]
                ),
            )
            .all()
        )

        logger.info(
            "Stored contradiction rows: %d",
            len(stored_rows),
        )

        for row in stored_rows:
            logger.info(
                "Pair=(%s, %s), contradiction=%s, "
                "entailment=%s, neutral=%s, threshold=%s",
                row.article_1_id,
                row.article_2_id,
                row.contradiction_score,
                row.entailment_score,
                row.neutral_score,
                row.threshold_used,
            )

    except Exception:
        db.rollback()
        logger.exception(
            "Contradiction storage test failed."
        )
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()