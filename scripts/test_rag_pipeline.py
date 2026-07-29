# scripts/test_rag_pipeline.py — FULL REPLACEMENT
import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import SessionLocal
from src.vector_storage.chroma_manager import ChromaManager
from src.generation.rag_engine import NewsGenerationEngine
from src.semantic_representation.embedding_generator import EmbeddingGenerator
from langchain_groq import ChatGroq

load_dotenv()


def extract_articles_from_chroma(raw_results):
    """
    Extracts clean article dictionaries from ChromaDB's raw query response,
    matching the shape generate_briefing() / ContradictionService expect:
    article_id, title, text, source.
    """
    extracted = []
    if isinstance(raw_results, dict) and "documents" in raw_results:
        docs = raw_results.get("documents", [[]])[0]
        metas = raw_results.get("metadatas", [[]])[0] if raw_results.get("metadatas") else []
        ids = raw_results.get("ids", [[]])[0] if raw_results.get("ids") else []

        for idx, text in enumerate(docs):
            meta = metas[idx] if idx < len(metas) and metas[idx] else {}
            article_id = ids[idx] if idx < len(ids) else None

            extracted.append({
                "article_id": int(article_id) if article_id is not None else None,
                "title": meta.get("title", f"Article {idx + 1}"),
                "text": text,
                "source": meta.get("source", "Unknown"),
            })
    elif isinstance(raw_results, list):
        extracted = raw_results
    return extracted


def main():
    print("=== Testing News Intelligence RAG Pipeline ===")

    db = SessionLocal()  # required now — generate_briefing() saves contradiction results
    try:
        embedder = EmbeddingGenerator()
        chroma = ChromaManager()

        query = "What are the latest updates in technology?"
        print(f"\n1. Converting query to embedding and searching ChromaDB: '{query}'...")

        query_embedding = embedder.generate_embedding(query)
        raw_docs = chroma.search_articles(query_embedding=query_embedding, top_k=5)

        retrieved_articles = extract_articles_from_chroma(raw_docs)
        print(f"   Successfully extracted {len(retrieved_articles)} articles from ChromaDB.")

        print("\n2. Initializing Groq LLM (Llama 3.3 70B)...")
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        rag_engine = NewsGenerationEngine(db=db, llm_model=llm)

        print("\n3. Generating briefing (trust + contradiction computed internally)...")
        briefing = rag_engine.generate_briefing(
            question=query,
            retrieved_articles=retrieved_articles,
            contradiction_threshold=0.50,
        )
        print("\n--- FINAL BRIEFING ---")
        print(briefing)

    finally:
        db.close()


if __name__ == "__main__":
    main()

# To test run:
# python scripts/test_rag_pipeline.py