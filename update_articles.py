import sys
from datetime import datetime
from sqlalchemy import func

from src.database.connection import init_db, SessionLocal
from src.database.models import RawArticles
from src.preprocessing.text_cleaner import TextCleaner
from src.preprocessing.language_detector import LanguageDetector
from src.enrichment.data_enricher import DataEnricher
from spacy_entity_extractor import SpacyEntityExtractor

print("=" * 60)
print("🔄 UPDATING EXISTING ARTICLES")
print("=" * 60)

# Initialize everything
init_db()
db = SessionLocal()
cleaner = TextCleaner()
detector = LanguageDetector()
enricher = DataEnricher()
extractor = SpacyEntityExtractor()

# Get articles without language
articles = db.query(RawArticles).filter(
    (RawArticles.language.is_(None)) | 
    (RawArticles.language == '')
).all()

print(f"\n📊 Found {len(articles)} articles to update")

if not articles:
    print("✅ All articles already have language!")
    db.close()
    exit()

print(f"⏳ Processing...\n")

updated = 0

for idx, article in enumerate(articles, 1):
    try:
        # Get text
        title = article.title or ''
        description = article.description or ''
        content = article.content or ''
        raw_text = f"{title} {description} {content}"
        
        if not raw_text.strip():
            continue
        
        # Clean text
        cleaned = cleaner.clean(raw_text)
        if not cleaned['has_content']:
            continue
        
        # Detect language
        lang = detector.detect(cleaned['cleaned_text'])
        article.language = lang['language']
        article.language_confidence = lang['confidence']
        
        # Extract entities
        entities = extractor.extract_from_article(title, description, content)
        article.entities = entities.get('entities', [])
        
        # Enrich data
        enrichment = enricher.enrich_article(title, description, content)
        article.sentiment = enrichment.get('sentiment', {})
        article.primary_topic = enrichment.get('primary_topic', 'general')
        article.topics = enrichment.get('topics', [])
        article.keyphrases = enrichment.get('keyphrases', [])
        article.readability = enrichment.get('readability', {})
        article.quality_score = enrichment.get('quality_score', 0)
        article.language_complexity = enrichment.get('language_complexity', {})
        article.enrichment_summary = enrichment.get('enrichment_summary', '')
        article.enriched_at = datetime.utcnow()
        
        # Cleaned data
        article.cleaned_title = cleaner.clean(title)['cleaned_text']
        article.cleaned_content = cleaned['cleaned_text']
        article.word_count = cleaned['word_count']
        article.character_count = cleaned['character_count']
        article.sentence_count = cleaned['sentence_count']
        article.avg_word_length = cleaned['avg_word_length']
        
        article.preprocessing_status = 'completed'
        article.processed_at = datetime.utcnow()
        
        updated += 1
        
        # Show progress
        if idx % 10 == 0:
            print(f"✅ Processed {idx}/{len(articles)} articles...")
        
    except Exception as e:
        print(f"❌ Error on article {idx}: {str(e)[:60]}...")

# Commit
try:
    db.commit()
    print(f"\n" + "=" * 60)
    print(f"✅ UPDATED: {updated} articles")
    print("=" * 60)
except Exception as e:
    db.rollback()
    print(f"\n❌ Commit failed: {e}")

# Show statistics
print("\n📊 Language Distribution:")
langs = db.query(
    RawArticles.language,
    func.count(RawArticles.id)
).filter(
    RawArticles.language.isnot(None),
    RawArticles.language != ''
).group_by(RawArticles.language).all()

if langs:
    for lang, count in langs:
        print(f"  {lang}: {count}")
else:
    print("  ❌ No languages found!")

entities_count = db.query(RawArticles).filter(
    RawArticles.entities.isnot(None),
    RawArticles.entities != '[]'
).count()
total = db.query(RawArticles).count()
print(f"\n📊 Articles with entities: {entities_count}/{total}")

db.close()
print("\n" + "=" * 60)
print("✅ Done!")