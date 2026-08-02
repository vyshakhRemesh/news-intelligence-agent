# main.py
import hashlib
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
import urllib3

from src.database.connection import SessionLocal, init_db
from src.database.models import RawArticles
from src.deduplication.deduplication_service import DeduplicationService
from src.enrichment.data_enricher import DataEnricher
from src.generation.rag_engine import NewsGenerationEngine
from src.ingestion.aggregator import NewsAggregator
from src.preprocessing.language_detector import LanguageDetector
from src.preprocessing.spacy_entity_extractor import SpacyEntityExtractor
from src.preprocessing.text_cleaner import TextCleaner
from src.recommendation.recommendation_service import RecommendationService
from src.recommendation.trust_score import TrustScore
from src.semantic_representation.embedding_generator import EmbeddingGenerator
from src.topic_modeling.topic_service import TopicService
from src.vector_storage.chroma_manager import ChromaManager


os.environ["SSL_CERT_FILE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["PGSSLMODE"] = "disable"

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            "logs/pipeline.log",
            encoding="utf-8",
        ),
    ],
)

logger = logging.getLogger(__name__)


def parse_iso_date(date_value):
    """Parse article dates from API and RSS sources."""

    if not date_value:
        return datetime.now(timezone.utc)

    if isinstance(date_value, datetime):
        return date_value

    date_text = str(date_value).strip()

    try:
        return datetime.fromisoformat(
            date_text.replace("Z", "+00:00")
        )
    except ValueError:
        pass

    rss_formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]

    for date_format in rss_formats:
        try:
            return datetime.strptime(
                date_text,
                date_format,
            )
        except ValueError:
            continue

    logger.warning(
        "Could not parse date %r; using current time.",
        date_value,
    )

    return datetime.now(timezone.utc)


class EnhancedPipeline:
    def __init__(self, db=None):
        """Initialize all pipeline components."""

        self.db = db
        self.aggregator = NewsAggregator()
        self.text_cleaner = TextCleaner()
        self.language_detector = LanguageDetector()
        self.data_enricher = DataEnricher()
        self.embedding_generator = EmbeddingGenerator()
        self.chroma_manager = ChromaManager()
        

        try:
            self.entity_extractor = SpacyEntityExtractor(
                model_name="en_core_web_sm"
            )
            logger.info("spaCy Entity Extractor initialized")
        except Exception as exc:
            logger.warning("spaCy not available: %s", exc)
            self.entity_extractor = SpacyEntityExtractor()

        self.stats = {
            "total_fetched": 0,
            "stored": 0,
            "skipped": 0,
            "errors": 0,
        }

    def run(
        self,
        category: str = "general",
        page_size: int = 100,
    ):
        """Run the complete news intelligence pipeline."""

        logger.info("=" * 60)
        logger.info("NEWS INTELLIGENCE AGENT")
        logger.info(
            "Category: %s | Page Size: %s",
            category,
            page_size,
        )
        logger.info("=" * 60)

        init_db()
        self.db = SessionLocal()
        self.topic_service = TopicService(db=self.db)
        logger.info("Database ready")

        try:
            articles_data = self.aggregator.fetch_all()

            if not articles_data:
                logger.warning("No articles fetched")
                return

            self.stats["total_fetched"] = len(articles_data)

            logger.info(
                "Total articles fetched: %d",
                len(articles_data),
            )

        except Exception as exc:
            logger.error(
                "Error fetching articles: %s",
                exc,
                exc_info=True,
            )
            self.stats["errors"] += 1
            return

        for data in articles_data:
            try:
                url = data.get("url")

                if not url:
                    continue

                article = self._store_article(data)

                if article is None:
                    continue

                self._process_article(article, data)
                self.db.commit()

            except Exception as exc:
                self.db.rollback()

                logger.error(
                    "Error processing article: %s",
                    exc,
                    exc_info=True,
                )

                self.stats["errors"] += 1

        logger.info(
            "Successfully processed and committed %d articles",
            self.stats["stored"],
        )

        try:
            logger.info("=" * 60)
            logger.info("Starting BERTopic Topic Modeling...")
            logger.info("=" * 60)

            self.topic_service.run()
            logger.info("BERTopic completed successfully.")

            self.run_recommendation()
            self.run_deduplication()
            # self.run_rag_pipeline()

            logger.info("Pipeline stages completed successfully.")

        except Exception as exc:
            self.db.rollback()

            logger.error(
                "Intelligence pipeline stage failed: %s",
                exc,
                exc_info=True,
            )

            self.stats["errors"] += 1

        self._show_stats()

        logger.info("=" * 60)
        logger.info("Pipeline execution completed")

    def run_deduplication(self):
        """Identify semantic duplicates and mark them in PostgreSQL."""

        logger.info("=" * 60)
        logger.info("SEMANTIC DEDUPLICATION")
        logger.info("=" * 60)

        deduplication_service = DeduplicationService(
            db=self.db,
            chroma_manager=self.chroma_manager,
        )

        duplicates = deduplication_service.preview_duplicates()

        logger.info(
            "Found %d duplicate candidates.",
            len(duplicates),
        )

        updated = deduplication_service.apply_duplicates(
            duplicates
        )

        logger.info(
            "Marked %d duplicate articles.",
            updated,
        )

        return updated

    def _store_article(
        self,
        data: Dict,
    ) -> Optional[RawArticles]:
        """
        Store an article while preserving cross-source perspectives.

        Rules:
        - Same URL + same source: skip.
        - Same URL + different source: keep.
        - Semantic duplicate decisions happen later.
        """

        url = data.get("url")

        if not url:
            return None

        source_name = data.get("source_name", "Unknown")

        existing_same_source = (
            self.db.query(RawArticles)
            .filter(
                RawArticles.url == url,
                RawArticles.source_name == source_name,
            )
            .first()
        )

        if existing_same_source:
            self.stats["skipped"] += 1

            logger.debug(
                "Skipped true duplicate: %s from %s",
                url,
                source_name,
            )

            return None

        existing_other_source = (
            self.db.query(RawArticles)
            .filter(RawArticles.url == url)
            .first()
        )

        published_at = data.get(
            "published_at",
            datetime.now(timezone.utc),
        )

        if isinstance(published_at, str):
            published_at = parse_iso_date(published_at)

        content = (
            data.get("content", "")
            or data.get("description", "")
        )

        content_hash = (
            hashlib.md5(content.encode("utf-8")).hexdigest()
            if content
            else None
        )

        source_type = str(
            data.get("source_type", "API")
        ).upper()

        article = RawArticles(
            title=data.get("title", ""),
            author=data.get("author", ""),
            source_name=source_name,
            source_type=source_type,
            description=data.get("description", ""),
            content=data.get("content", ""),
            url=url,
            published_at=published_at,
            content_hash=content_hash,
            is_duplicate=False,
            duplicate_of_id=None,
        )

        self.db.add(article)
        self.db.flush()
        self.db.commit()

        self.stats["stored"] += 1

        if existing_other_source:
            logger.info(
                "Stored duplicate perspective: %s from %s "
                "(original: %s)",
                url,
                source_name,
                existing_other_source.source_name,
            )

        return article

    def _process_article(
        self,
        article: RawArticles,
        data: Dict,
    ):
        """Process a single article through the NLP pipeline."""

        try:
            title = data.get("title", "")
            description = data.get("description", "")
            content = data.get("content", "")
            raw_text = f"{title} {description} {content}"

            if not raw_text.strip():
                article.preprocessing_status = "failed"
                return

            cleaned = self.text_cleaner.clean(raw_text)

            if not cleaned["has_content"]:
                article.preprocessing_status = "failed"
                return

            lang_result = self.language_detector.detect(
                cleaned["cleaned_text"]
            )

            article.language = lang_result["language"]
            article.language_confidence = lang_result["confidence"]

            entities_result = (
                self.entity_extractor.extract_from_article(
                    title=title,
                    description=description,
                    content=content,
                )
            )

            article.entities = entities_result.get("entities", [])

            enrichment = self.data_enricher.enrich_article(
                title=title,
                description=description,
                content=content,
            )

            article.sentiment = enrichment.get("sentiment", {})
            article.keyphrases = enrichment.get("keyphrases", [])
            article.readability = enrichment.get("readability", {})
            article.quality_score = enrichment.get(
                "quality_score",
                0,
            )
            article.language_complexity = enrichment.get(
                "language_complexity",
                {},
            )
            article.enrichment_summary = enrichment.get(
                "enrichment_summary",
                "",
            )
            article.enriched_at = datetime.now(timezone.utc)

            article.cleaned_title = self.text_cleaner.clean(
                title
            )["cleaned_text"]
            article.cleaned_content = cleaned["cleaned_text"]
            article.word_count = cleaned["word_count"]
            article.character_count = cleaned["character_count"]
            article.sentence_count = cleaned["sentence_count"]
            article.avg_word_length = cleaned["avg_word_length"]

            try:
                embedding = (
                    self.embedding_generator.generate_embedding(
                        cleaned["cleaned_text"]
                    )
                )

                if embedding:
                    self.chroma_manager.store_article(
                        article_id=article.id,
                        text=cleaned["cleaned_text"],
                        embedding=embedding,
                        metadata={
                            "title": title or "",
                            "source": article.source_name or "Unknown",
                            "language": article.language or "unknown",
                            "quality_score": article.quality_score or 0,
                        },
                    )

                    logger.info(
                        "Embedding stored for article %s",
                        article.id,
                    )

            except Exception as exc:
                logger.error(
                    "Embedding failed for article %s: %s",
                    article.id,
                    exc,
                    exc_info=True,
                )

            article.preprocessing_status = "completed"
            article.processed_at = datetime.now(timezone.utc)

            logger.info(
                "Article %s: %s...",
                article.id,
                title[:50],
            )

            if article.entities:
                logger.info(
                    "   Entities: %d found",
                    len(article.entities),
                )

            if article.enrichment_summary:
                logger.info(
                    "   Enrichment: %s",
                    article.enrichment_summary,
                )

        except Exception as exc:
            logger.error(
                "Error processing article %s: %s",
                article.id,
                exc,
                exc_info=True,
            )

            article.preprocessing_status = "failed"

    def _show_stats(self):
        """Display pipeline statistics."""

        logger.info("=" * 60)
        logger.info("PIPELINE SUMMARY")
        logger.info("=" * 60)

        logger.info(
            "Articles fetched: %d",
            self.stats["total_fetched"],
        )
        logger.info(
            "Articles stored: %d",
            self.stats["stored"],
        )
        logger.info(
            "Articles skipped: %d",
            self.stats.get("skipped", 0),
        )
        logger.info(
            "Errors: %d",
            self.stats["errors"],
        )

        if self.db:
            try:
                total = self.db.query(RawArticles).count()

                processed = (
                    self.db.query(RawArticles)
                    .filter(
                        RawArticles.preprocessing_status
                        == "completed"
                    )
                    .count()
                )

                duplicates = (
                    self.db.query(RawArticles)
                    .filter(
                        RawArticles.is_duplicate.is_(True)
                    )
                    .count()
                )

                logger.info(
                    "Total articles in DB: %d",
                    total,
                )
                logger.info(
                    "Processed articles: %d",
                    processed,
                )
                logger.info(
                    "Duplicate articles marked: %d",
                    duplicates,
                )

            except Exception as exc:
                logger.debug(
                    "Could not get DB stats: %s",
                    exc,
                )

    def run_recommendation(self):
        """
        Score processed, non-duplicate articles and
        display the highest-ranked recommendations.
        """

        logger.info("=" * 60)
        logger.info("RECOMMENDATION ENGINE")
        logger.info("=" * 60)

        articles = (
            self.db.query(RawArticles)
            .filter(
                RawArticles.preprocessing_status == "completed",
                RawArticles.is_duplicate.is_(False),
            )
            .all()
        )

        if not articles:
            logger.warning("No processed articles found.")
            return []

        user = {
            "preferred_topics": [
                "technology",
                "artificial intelligence",
                "science",
            ],
            "preferred_sources": [
                "Reuters",
                "BBC News",
                "Nature",
            ],
        }

        service = RecommendationService(db=self.db)

        ranked = service.recommend(
            articles=articles,
            user=user,
            save_results=True,
        )
        self.db.commit()

        logger.info(
        "Recommendation results committed to database."
        )

        logger.info(
            "Recommendation completed (%d articles scored).",
            len(ranked),
        )

        logger.info("")
        logger.info("TOP RECOMMENDED ARTICLES")
        logger.info("-" * 60)

        for index, item in enumerate(
            ranked[:5],
            start=1,
        ):
            article = item["article"]
            scores = item["scores"]

            logger.info(
                "%d. %s",
                index,
                article.title,
            )

            logger.info(
                "   Source: %s | Topic: %s | "
                "Recommendation: %.2f | Trust: %.2f",
                article.source_name,
                article.primary_topic,
                scores["recommendation_score"],
                scores["trust_score"],
            )

        logger.info("-" * 60)

        return ranked

    def run_rag_pipeline(self):
        """
        Run ChromaDB retrieval, trust scoring,
        contradiction detection and RAG briefing generation.
        """

        logger.info("=" * 60)
        logger.info("RAG AND CONTRADICTION ANALYSIS")
        logger.info("=" * 60)

        question = (
            "What are the latest important developments "
            "in technology and artificial intelligence?"
        )

        search_results = self.chroma_manager.search_by_text(
            query_text=question,
            top_k=5,
            embedder=self.embedding_generator,
        )

        documents = search_results.get(
            "documents",
            [[]],
        )[0] or []
        metadatas = search_results.get(
            "metadatas",
            [[]],
        )[0] or []
        ids = search_results.get(
            "ids",
            [[]],
        )[0] or []

        retrieved_articles = []

        for article_id, document, metadata in zip(
            ids,
            documents,
            metadatas,
        ):
            metadata = metadata or {}

            try:
                postgres_article_id = int(article_id)
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping invalid article ID from ChromaDB: %s",
                    article_id,
                )
                continue

            article_data = {
                "article_id": postgres_article_id,
                "title": metadata.get("title", "Untitled"),
                "source": metadata.get("source", "Unknown"),
                "topic": metadata.get("topic", "general"),
                "quality_score": metadata.get(
                    "quality_score",
                    0,
                ),
                "text": document,
            }

            article_data["trust_score"] = TrustScore.calculate(
                article_data
            )

            retrieved_articles.append(article_data)

        if not retrieved_articles:
            logger.warning(
                "No relevant articles were retrieved."
            )
            return None

        logger.info(
            "Retrieved %d articles for RAG.",
            len(retrieved_articles),
        )

        logger.info("ARTICLES SENT FOR CONTRADICTION CHECK")

        for index, article in enumerate(
            retrieved_articles,
            start=1,
        ):
            logger.info(
                "%d. %s | Source: %s | Trust: %s",
                index,
                article["title"],
                article["source"],
                article["trust_score"],
            )

        rag_engine = NewsGenerationEngine(db=self.db)

        result = rag_engine.generate_briefing(
            question=question,
            retrieved_articles=retrieved_articles,
            contradiction_threshold=0.50,
        )

        logger.info("")
        logger.info("GENERATED NEWS BRIEFING")
        logger.info("-" * 60)
        logger.info(result)
        logger.info("-" * 60)

        return result

    def close(self):
        """Close all connections."""

        if self.db:
            try:
                self.db.close()
                logger.info("Database connection closed")
            except Exception as exc:
                logger.debug(
                    "Error closing database: %s",
                    exc,
                )


def run_pipeline():
    """Run the enhanced pipeline."""

    api_keys = {
        "NEWS_API_KEY": os.getenv("NEWS_API_KEY"),
        "GNEWS_API_KEY": os.getenv("GNEWS_API_KEY"),
        "CURRENTS_API_KEY": os.getenv("CURRENTS_API_KEY"),
    }

    missing_keys = [
        key
        for key, value in api_keys.items()
        if not value
        or value == f"your_{key.lower()}_here"
    ]

    if missing_keys:
        logger.warning("=" * 60)
        logger.warning("Missing API Keys:")

        for key in missing_keys:
            logger.warning("   - %s", key)

        logger.warning("=" * 60)
        logger.info("RSS feeds will work without API keys.")
        logger.info("=" * 60)

    pipeline = EnhancedPipeline()

    try:
        pipeline.run()

    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")

    except Exception as exc:
        logger.error(
            "Pipeline failed: %s",
            exc,
            exc_info=True,
        )

    finally:
        pipeline.close()


if __name__ == "__main__":
    run_pipeline()