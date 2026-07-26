# main.py
import os
import sys
import io
import json
import urllib3
import requests
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from src.ingestion.newsapi_client import NewsAPIClient
from src.database.connection import init_db, SessionLocal
from src.database.models import RawArticles
from src.preprocessing.text_cleaner import TextCleaner
from src.preprocessing.language_detector import LanguageDetector
from src.enrichment.data_enricher import DataEnricher
from src.semantic_representation.embedding_generator import EmbeddingGenerator
from src.vector_storage.chroma_manager import ChromaManager
from src.preprocessing.spacy_entity_extractor import SpacyEntityExtractor
from src.ingestion.aggregator import NewsAggregator
from src.topic_modeling.topic_service import TopicService
from src.recommendation.recommendation_service import RecommendationService
from src.generation.rag_engine import NewsGenerationEngine

# ============================================
# FIX SSL CERTIFICATE ISSUES
# ============================================
os.environ['SSL_CERT_FILE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['PGSSLMODE'] = 'disable'

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

# Create logs folder if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/pipeline.log", encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)


def parse_iso_date(date_str):
    """
    Parse various date formats from APIs and RSS feeds.
    Handles ISO 8601, RFC 822 (RSS), and datetime objects.
    """
    if not date_str:
        return datetime.utcnow()
    
    # Already a datetime object
    if isinstance(date_str, datetime):
        return date_str
    
    # Clean string
    date_str = str(date_str).strip()
    
    formats = [
        "%Y-%m-%dT%H:%M:%S",           # NewsAPI: 2026-06-06T03:52:00 (Z stripped)
        "%Y-%m-%dT%H:%M:%S%z",          # ISO with timezone: +00:00
        "%Y-%m-%dT%H:%M:%SZ",           # ISO with Z suffix
        "%a, %d %b %Y %H:%M:%S %z",     # RSS RFC 822: Mon, 06 Jun 2026 03:52:00 +0000
        "%a, %d %b %Y %H:%M:%S %Z",     # RSS with named timezone
    ]
    
    # Try stripping Z and parsing
    cleaned = date_str.replace("Z", "+00:00")
    
    for fmt in formats:
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    
    # Fallback
    logger.warning(f"Could not parse date: {date_str}, using current time")
    return datetime.utcnow()


class EnhancedPipeline:
    def __init__(self):
        """Initialize all pipeline components"""
        # Database session
        self.db = None
        
        # Aggregator (multi-source with circuit breakers)
        self.aggregator = NewsAggregator()
        
        # Preprocessing
        self.text_cleaner = TextCleaner()
        self.language_detector = LanguageDetector()
        
        # Enrichment
        self.data_enricher = DataEnricher()

        self.embedding_generator = EmbeddingGenerator()
        self.chroma_manager = ChromaManager()

        self.topic_service = TopicService()
        
        # spaCy
        try:
            self.entity_extractor = SpacyEntityExtractor(model_name="en_core_web_sm")
            logger.info("spaCy Entity Extractor initialized")
        except Exception as e:
            logger.warning(f"spaCy not available: {e}")
            self.entity_extractor = SpacyEntityExtractor()
        
        # Stats
        self.stats = {
            'total_fetched': 0,
            'stored': 0,
            'skipped': 0,
            'errors': 0
        }
    
    def run(self, category: str = "general", page_size: int = 100):
        """Run the enhanced pipeline"""
        logger.info("=" * 60)
        logger.info("Starting Enhanced News Intelligence Pipeline")
        logger.info(f"Category: {category}, Page Size: {page_size}")
        logger.info("=" * 60)
        
        # Initialize database
        init_db()
        self.db = SessionLocal()
        logger.info("Database ready")
        
        # Fetch articles from all sources (NO deduplication at ingestion)
        try:
            articles_data = self.aggregator.fetch_all()
            if not articles_data:
                logger.warning("No articles fetched")
                return
            self.stats['total_fetched'] = len(articles_data)
            logger.info(f"Total articles fetched: {len(articles_data)}")
        except Exception as e:
            logger.error(f"Error fetching articles: {e}")
            return
        
        # Process each article
        for data in articles_data:
            try:
                url = data.get("url")

                if not url:
                    continue

                article = self._store_article(data)

                if not article:
                    continue

                self._process_article(article, data)

                # Commit each successfully processed article
                self.db.commit()

            except Exception as e:
                # Clear the failed PostgreSQL transaction
                self.db.rollback()

                logger.error(
                    "Error processing article: %s",
                    e,
                    exc_info=True,
                )

                self.stats["errors"] += 1
                
        # Commit all changes
        logger.info(
            "Successfully processed and committed %s articles",
            self.stats["stored"],
        )
        # ============================================
        # BERTopic Topic Modeling
        # ============================================
        try:
            logger.info("=" * 60)
            logger.info("Starting BERTopic Topic Modeling...")
            logger.info("=" * 60)
            self.topic_service.run()
            logger.info("BERTopic completed successfully.")

            self.test_recommendation()
            self.test_rag_pipeline()

            logger.info("Pipeline completed successfully!")

        except Exception as e:
            logger.error(f"BERTopic failed: {e}", exc_info=True)
        
        # Show stats
        self._show_stats()
        logger.info("=" * 60)
        logger.info("Pipeline execution completed")
    
    def _store_article(self, data: Dict) -> Optional[RawArticles]:
        """
        Store article with smart duplicate handling.
        
        Rules:
        - Same URL + same source = TRUE DUPLICATE → skip
        - Same URL + different source = DIFFERENT PERSPECTIVE → keep, mark as duplicate
        - New URL → keep normally
        
        This preserves multiple sources for contradiction detection.
        """
        url = data.get('url')
        if not url:
            return None
        
        source_name = data.get('source_name', 'Unknown')
        
        # Rule 1: Same URL + same source = true duplicate, skip
        existing_same_source = self.db.query(RawArticles).filter(
            RawArticles.url == url,
            RawArticles.source_name == source_name
        ).first()
        
        if existing_same_source:
            self.stats['skipped'] += 1
            logger.debug(f"Skipped true duplicate: {url} from {source_name}")
            return None
        
        # Rule 2: Same URL from different source = keep for contradiction detection
        existing_other_source = self.db.query(RawArticles).filter(
            RawArticles.url == url
        ).first()
        
        # Parse published_at (handle string or datetime)
        published_at = data.get('published_at', datetime.now(timezone.utc))
        if isinstance(published_at, str):
            published_at = parse_iso_date(published_at)
        
        # Generate content hash for event grouping (used by contradiction detection later)
        content = data.get('content', '') or data.get('description', '')
        content_hash = hashlib.md5(content.encode()).hexdigest() if content else None
        
        # Normalize source_type to uppercase
        source_type = str(data.get('source_type', 'API')).upper()
        
        # Create article
        article = RawArticles(
            title=data.get('title', ''),
            author=data.get('author', ''),
            source_name=source_name,
            source_type=source_type,
            description=data.get('description', ''),
            content=data.get('content', ''),
            url=url,
            published_at=published_at,
            content_hash=content_hash,
            is_duplicate=existing_other_source is not None,
            duplicate_of_id=existing_other_source.id if existing_other_source else None
        )
        
        self.db.add(article)
        self.db.flush()
        self.db.commit()
        self.stats['stored'] += 1
        
        if existing_other_source:
            logger.info(f"Stored duplicate perspective: {url} from {source_name} (original: {existing_other_source.source_name})")
        
        return article
    
    def _process_article(self, article: RawArticles, data: Dict):
        """Process a single article with NLP pipeline"""
        try:
            title = data.get('title', '')
            description = data.get('description', '')
            content = data.get('content', '')
            raw_text = f"{title} {description} {content}"
            
            if not raw_text.strip():
                article.preprocessing_status = 'failed'
                return
            
            # 1. Clean text
            cleaned = self.text_cleaner.clean(raw_text)
            if not cleaned['has_content']:
                article.preprocessing_status = 'failed'
                return
            
            # 2. Detect language
            lang_result = self.language_detector.detect(cleaned['cleaned_text'])
            article.language = lang_result['language']
            article.language_confidence = lang_result['confidence']
            
            # 3. Extract entities (spaCy)
            entities_result = self.entity_extractor.extract_from_article(
                title=title,
                description=description,
                content=content
            )
            article.entities = entities_result.get('entities', [])
            
            # 4. Enrich data
            enrichment = self.data_enricher.enrich_article(
                title=title,
                description=description,
                content=content
            )
            article.sentiment = enrichment.get('sentiment', {})
            article.primary_topic = enrichment.get('primary_topic', 'general')
            article.topics = enrichment.get('topics', [])
            article.keyphrases = enrichment.get('keyphrases', [])
            article.readability = enrichment.get('readability', {})
            article.quality_score = enrichment.get('quality_score', 0)
            article.language_complexity = enrichment.get('language_complexity', {})
            article.enrichment_summary = enrichment.get('enrichment_summary', '')
            article.enriched_at = datetime.now(timezone.utc)
            
            # 5. Update article with cleaned data
            article.cleaned_title = self.text_cleaner.clean(title)['cleaned_text']
            article.cleaned_content = cleaned['cleaned_text']
            article.word_count = cleaned['word_count']
            article.character_count = cleaned['character_count']
            article.sentence_count = cleaned['sentence_count']
            article.avg_word_length = cleaned['avg_word_length']
            
            # 6. Generate embedding and store in ChromaDB
            try:
                embedding = self.embedding_generator.generate_embedding(
                    cleaned['cleaned_text']
                )

                if embedding:
                    self.chroma_manager.store_article(
                        article_id=article.id,
                        text=cleaned['cleaned_text'],
                        embedding=embedding,
                        metadata={
                            "title": title,
                            "source": article.source_name,
                            "language": article.language,
                            "topic": article.primary_topic,
                            "quality_score": article.quality_score
                        }
                    )
                    logger.info(f"Embedding stored for article {article.id}")
            except Exception as e:
                logger.error(f"Embedding failed for article {article.id}: {e}")
            
            article.preprocessing_status = 'completed'
            article.processed_at = datetime.now(timezone.utc)
            
            # Log
            logger.info(f"Article {article.id}: {title[:50]}...")
            if article.entities:
                logger.info(f"   Entities: {len(article.entities)} found")
            if article.enrichment_summary:
                logger.info(f"   Enrichment: {article.enrichment_summary}")
            
        except Exception as e:
            logger.error(f"Error processing article {article.id}: {e}")
            article.preprocessing_status = 'failed'
    
    def _show_stats(self):
        """Display pipeline statistics"""
        logger.info("Pipeline Statistics:")
        logger.info(f"  - Articles fetched: {self.stats['total_fetched']}")
        logger.info(f"  - Articles stored: {self.stats['stored']}")
        logger.info(f"  - Articles skipped (true duplicates): {self.stats.get('skipped', 0)}")
        logger.info(f"  - Errors: {self.stats['errors']}")
        
        # Database stats
        if self.db:
            try:
                total = self.db.query(RawArticles).count()
                processed = self.db.query(RawArticles).filter(
                    RawArticles.preprocessing_status == 'completed'
                ).count()
                duplicates = self.db.query(RawArticles).filter(
                    RawArticles.is_duplicate == True
                ).count()
                logger.info(f"  - Total articles in DB: {total}")
                logger.info(f"  - Processed: {processed}")
                logger.info(f"  - Duplicate perspectives kept: {duplicates}")
            except Exception as e:
                logger.debug(f"Could not get DB stats: {e}")

    def test_recommendation(self):
        """
        Temporary testing function.
        Uses real articles from PostgreSQL and runs the
        recommendation engine.
        """
        logger.info("=" * 60)
        logger.info("TESTING RECOMMENDATION ENGINE")
        logger.info("=" * 60)

        articles = (
            self.db.query(RawArticles)
            .filter(RawArticles.preprocessing_status == "completed")
            .limit(10)
            .all()
        )

        if not articles:
            logger.warning("No processed articles found.")
            return

        user = {
            "preferred_topics": [
                "technology",
                "artificial intelligence",
                "science"
            ],
            "preferred_sources": [
                "Reuters",
                "BBC News",
                "Nature"
            ]
        }

        service = RecommendationService(
            db=self.db
        )

        ranked = service.recommend(
            articles=articles,
            user=user,
            save_results=True,
        )

        logger.info(
            f"Saved recommendation scores "
            f"for {len(ranked)} articles."
        )

        logger.info("")
        logger.info("TOP RECOMMENDED ARTICLES")
        logger.info("-" * 60)

        for i, item in enumerate(ranked, start=1):

            article = item["article"]
            scores = item["scores"]

            logger.info(f"{i}. {article.title}")
            logger.info(f"   Source : {article.source_name}")
            logger.info(f"   Topic  : {article.primary_topic}")
            logger.info(f"   Recommendation : {scores['recommendation_score']}")
            logger.info(f"   Trust          : {scores['trust_score']}")
            logger.info(f"   Confidence     : {scores['confidence_score']}")
            logger.info(f"   Freshness      : {scores['freshness_score']}")
            logger.info(f"   Interest       : {scores['interest_score']}")
            logger.info(f"   Source Pref    : {scores['source_preference_score']}")
            logger.info("-" * 60)

    def test_rag_pipeline(self):
        """
        Temporary end-to-end test for:
        ChromaDB retrieval -> trust score -> contradiction detection
        -> RAG briefing generation.
        """

        logger.info("=" * 60)
        logger.info("TESTING RAG AND CONTRADICTION PIPELINE")
        logger.info("=" * 60)

        question = (
            "What are the latest important developments "
            "in technology and artificial intelligence?"
        )

        # Retrieve relevant articles from ChromaDB
        search_results = self.chroma_manager.search_by_text(
            query_text=question,
            top_k=5,
            embedder=self.embedding_generator,
        )

        documents = search_results.get("documents", [[]])[0] or []
        metadatas = search_results.get("metadatas", [[]])[0] or []
        ids = search_results.get("ids", [[]])[0] or []

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

            retrieved_articles.append({
                "article_id": postgres_article_id,
                "title": metadata.get("title", "Untitled"),
                "source": metadata.get("source", "Unknown"),
                "topic": metadata.get("topic", "general"),
                "quality_score": metadata.get("quality_score", 0),
                "text": document,
            })

        if not retrieved_articles:
            logger.warning(
                "No relevant articles were retrieved for RAG testing."
            )
            return

        logger.info(
            f"Retrieved {len(retrieved_articles)} articles for RAG."
        )

        logger.info("ARTICLES SENT FOR CONTRADICTION CHECK")

        for index, article in enumerate(retrieved_articles, start=1):
            logger.info(
                "%d. %s | Source: %s",
                index,
                article["title"],
                article["source"],
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
    
    def close(self):
        """Close all connections"""
        if self.db:
            try:
                self.db.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.debug(f"Error closing database: {e}")


# ============================================
# MAIN ENTRY POINT
# ============================================

def run_pipeline():
    """Run the enhanced pipeline"""
    # Check for API keys
    api_keys = {
        "NEWS_API_KEY": os.getenv("NEWS_API_KEY"),
        "GNEWS_API_KEY": os.getenv("GNEWS_API_KEY"),
        "CURRENTS_API_KEY": os.getenv("CURRENTS_API_KEY"),
    }
    
    missing_keys = [k for k, v in api_keys.items() if not v or v == f"your_{k.lower()}_here"]
    
    if missing_keys:
        logger.warning("=" * 60)
        logger.warning("Missing API Keys:")
        for key in missing_keys:
            logger.warning(f"   - {key}")
        logger.warning("=" * 60)
        logger.info("RSS feeds will work without API keys.")
        logger.info("=" * 60)
    
    pipeline = EnhancedPipeline()
    
    try:
        pipeline.run()
    except KeyboardInterrupt:
        logger.info("\nPipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
    finally:
        pipeline.close()


if __name__ == "__main__":
    run_pipeline()