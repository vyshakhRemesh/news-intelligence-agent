# main.py
import os
import sys
import io
import json
import urllib3
import requests
import logging
from datetime import datetime,timezone
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from src.ingestion.newsapi_client import NewsAPIClient
from src.database.connection import init_db, SessionLocal
from src.database.models import RawArticles
from src.preprocessing.text_cleaner import TextCleaner
from src.preprocessing.language_detector import LanguageDetector
from src.enrichment.data_enricher import DataEnricher
# from src.embedding.embedding_generator import EmbeddingGenerator
# from src.vector_db.chromadb_client import ChromaDBClient
from spacy_entity_extractor import SpacyEntityExtractor
from src.ingestion.aggregator import NewsAggregator

# ============================================
# FIX SSL CERTIFICATE ISSUES
# ============================================
os.environ['SSL_CERT_FILE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['PGSSLMODE'] = 'disable'

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()


# Configure the global logging layout for our terminal
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pipeline.log', encoding='utf-8')
    ]
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

class EnhancedPipeline:
    def __init__(self):
        """Initialize all pipeline components"""
        # Database session
        self.db = None
        
        # Aggregator (multi-source)
        self.aggregator = NewsAggregator()
        
        # Preprocessing
        self.text_cleaner = TextCleaner()
        self.language_detector = LanguageDetector()
        
        # Enrichment
        self.data_enricher = DataEnricher()
        
        # Embeddings
        # try:
        #     self.embedding_generator = EmbeddingGenerator(model_name="all-MiniLM-L6-v2")
        #     if self.embedding_generator.is_available():
        #         logger.info(f"✅ Sentence Transformer initialized (dim: {self.embedding_generator.get_embedding_dimension()})")
        #     else:
        #         logger.warning("⚠️ Sentence Transformer not available")
        #         self.embedding_generator = None
        # except Exception as e:
        #     logger.warning(f"⚠️ Could not initialize Sentence Transformer: {e}")
        #     self.embedding_generator = None
        
        # ChromaDB
        # try:
        #     self.chromadb = ChromaDBClient(
        #         collection_name="news_articles",
        #         persist_directory="./chroma_db"
        #     )
        #     if self.chromadb.available:
        #         stats = self.chromadb.get_collection_stats()
        #         logger.info(f"✅ ChromaDB ready: {stats['vector_count']} vectors")
        #     else:
        #         logger.warning("⚠️ ChromaDB not available")
        #         self.chromadb = None
        # except Exception as e:
        #     logger.warning(f"⚠️ Could not initialize ChromaDB: {e}")
        #     self.chromadb = None
        
        # spaCy
        try:
            self.entity_extractor = SpacyEntityExtractor(model_name="en_core_web_sm")
            logger.info("✅ spaCy Entity Extractor initialized")
        except Exception as e:
            logger.warning(f"⚠️ spaCy not available: {e}")
            self.entity_extractor = SpacyEntityExtractor()
        
        # Stats
        self.stats = {
            'total_fetched': 0,
            'stored': 0,
            'chromadb_added': 0,
            'errors': 0
        }

    def run(self, category: str = "general", page_size: int = 100):
        """Run the enhanced pipeline"""
        logger.info("=" * 60)
        logger.info("Starting Enhanced News Intelligence Pipeline (tejas branch)")
        logger.info(f"Category: {category}, Page Size: {page_size}")
        logger.info("=" * 60)
        
        # Initialize database
        init_db()
        self.db = SessionLocal()
        logger.info("✅ Database ready")
        
        # Fetch articles from all sources
        try:
            articles_data = self.aggregator.fetch_all()
            if not articles_data:
                logger.warning("No articles fetched")
                return
            self.stats['total_fetched'] = len(articles_data)
            logger.info(f"📊 Total articles fetched: {len(articles_data)}")
        except Exception as e:
            logger.error(f"❌ Error fetching articles: {e}")
            return
        
        # Process each article
        for data in articles_data:
            try:
                url = data.get('url')
                if not url:
                    continue
                
                # Check if exists
                existing = self.db.query(RawArticles).filter(RawArticles.url == url).first()
                if existing:
                    continue
                
                # Create article
                article = RawArticles(
                    title=data.get('title', ''),
                    author=data.get('author', ''),
                    source_name=data.get('source_name', 'Unknown'),
                    description=data.get('description', ''),
                    content=data.get('content', ''),
                    url=url,
                    published_at=data.get('published_at', datetime.now(timezone.utc)),
                    source_type=data.get('source_type', 'api')
                )
                self.db.add(article)
                self.db.flush()
                
                # Process article
                self._process_article(article, data)
                self.stats['stored'] += 1
                
            except Exception as e:
                logger.error(f"Error processing article: {e}")
                self.stats['errors'] += 1
        
        # Commit
        try:
            self.db.commit()
            logger.info(f"✅ Stored {self.stats['stored']} new articles")
        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Database commit failed: {e}")
        
        # Show stats
        self._show_stats()
        logger.info("=" * 60)
        logger.info("Pipeline execution completed")
    
    def _process_article(self, article: RawArticles, data: Dict):
        """Process a single article"""
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
            
            # 6. Generate embedding
            # if self.embedding_generator and self.embedding_generator.is_available():
            #     try:
            #         embedding_data = self.embedding_generator.embed_article(
            #             title=title,
            #             description=description,
            #             content=content
            #         )
            #         if embedding_data and embedding_data.get('embedding'):
            #             article.embedding = embedding_data['embedding']
            #             article.embedding_model = embedding_data.get('model', 'all-MiniLM-L6-v2')
            #             article.embedding_dimension = embedding_data.get('dimension', 384)
                        
                        # Store in ChromaDB
                #         if self.chromadb and self.chromadb.available:
                #             metadata = {
                #                 'source': data.get('source_name', 'Unknown'),
                #                 'published_at': str(data.get('published_at', '')),
                #                 'language': article.language,
                #                 'primary_topic': article.primary_topic,
                #                 'quality_score': article.quality_score,
                #                 'source_type': data.get('source_type', 'api'),
                #                 'title': title
                #             }
                #             chromadb_id = self.chromadb.add_article(
                #                 article_id=article.id,
                #                 title=title,
                #                 content=content[:500] if content else title,
                #                 embedding=article.embedding,
                #                 metadata=metadata
                #             )
                #             if chromadb_id:
                #                 article.chromadb_id = chromadb_id
                #                 self.stats['chromadb_added'] += 1
                # except Exception as e:
                #     logger.error(f"Embedding generation failed: {e}")
            
            article.preprocessing_status = 'completed'
            article.processed_at = datetime.now(timezone.utc)
            
            # Log
            logger.info(f"✅ Article {article.id}: {title[:50]}...")
            if article.entities:
                logger.info(f"   Entities: {len(article.entities)} found")
            if article.enrichment_summary:
                logger.info(f"   Enrichment: {article.enrichment_summary}")
            
        except Exception as e:
            logger.error(f"Error processing article {article.id}: {e}")
            article.preprocessing_status = 'failed'
    

    def _show_stats(self):
        """Display pipeline statistics"""
        logger.info("📊 Pipeline Statistics:")
        logger.info(f"  - Articles fetched: {self.stats['total_fetched']}")
        logger.info(f"  - Articles stored: {self.stats['stored']}")
        logger.info(f"  - ChromaDB vectors: {self.stats['chromadb_added']}")
        logger.info(f"  - Errors: {self.stats['errors']}")
        
        # Database stats
        if self.db:
            try:
                total = self.db.query(RawArticles).count()
                processed = self.db.query(RawArticles).filter(
                    RawArticles.preprocessing_status == 'completed'
                ).count()
                logger.info(f"  - Total articles in DB: {total}")
                logger.info(f"  - Processed: {processed}")
            except Exception as e:
                logger.debug(f"Could not get DB stats: {e}")
    
    def close(self):
        """Close all connections"""
        if self.chromadb:
            try:
                self.chromadb.close()
            except:
                pass
        if self.db:
            try:
                self.db.close()
            except:
                pass


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
        logger.warning("⚠️  Missing API Keys:")
        for key in missing_keys:
            logger.warning(f"   - {key}")
        logger.warning("=" * 60)
        logger.info("RSS feeds will work without API keys.")
        logger.info("=" * 60)
    
    pipeline = EnhancedPipeline()
    
    try:
        pipeline.run()
    except KeyboardInterrupt:
        logger.info("\n⏹️ Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
    finally:
        pipeline.close()


if __name__ == "__main__":
    run_pipeline()