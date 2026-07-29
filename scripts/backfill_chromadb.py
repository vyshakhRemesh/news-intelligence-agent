from src.database.connection import SessionLocal
from src.database.models import RawArticles
from src.semantic_representation.embedding_generator import EmbeddingGenerator
from src.vector_storage.chroma_manager import ChromaManager

print("=" * 70)
print("BACKFILLING POSTGRESQL TO CHROMADB")
print("=" * 70)

db = SessionLocal()

embedding_generator = EmbeddingGenerator()
chroma = ChromaManager()

articles = db.query(RawArticles).all()

print(f"Found {len(articles)} articles.\n")

stored = 0
already = 0
failed = 0

for i, article in enumerate(articles, start=1):

    print(f"[{i}/{len(articles)}] Processing Article {article.id}")

    try:

        text = " ".join(
            filter(
                None,
                [
                    article.title,
                    article.description,
                    article.content
                ]
            )
        )

        if not text.strip():
            print("   Empty article. Skipped.")
            continue

        embedding = embedding_generator.generate_embedding(text)

        metadata = {
            "source": article.source_name or "Unknown",
            "topic": article.primary_topic or "general",
            "language": article.language or "unknown",
            "quality_score": article.quality_score or 0,
            "title": article.title
        }

        inserted = chroma.store_article(
            article_id=article.id,
            text=text,
            embedding=embedding,
            metadata=metadata
        )

        if inserted:
            stored += 1
            print("   Stored.")
        else:
            already += 1
            print("   Already exists.")

    except Exception as e:
        failed += 1
        print("   ERROR:", e)

print("\n")
print("=" * 70)
print("BACKFILL FINISHED")
print("=" * 70)

print("Stored :", stored)
print("Already Present :", already)
print("Failed :", failed)

print("Final Chroma Count :", chroma.count_articles())

db.close()