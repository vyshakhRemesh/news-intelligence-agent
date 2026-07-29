import sys
import os
from dotenv import load_dotenv

# Add project root directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vector_storage.chroma_manager import ChromaManager
from src.generation.rag_engine import NewsGenerationEngine
from src.semantic_representation.embedding_generator import EmbeddingGenerator


# Load variables from .env file
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Choose your LLM model ---
# Example using OpenAI:
# from langchain_openai import ChatOpenAI
# llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# Groq
from langchain_groq import ChatGroq

print("\nInitializing Groq LLM...")
llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

# Example using Local Ollama (Llama 3):
# from langchain_community.chat_models import ChatOllama
# llm = ChatOllama(model="llama3", temperature=0)


def extract_articles_from_chroma(raw_results):
    """
    Extracts clean article dictionaries from ChromaDB's raw query response.
    """
    extracted = []
    if isinstance(raw_results, dict) and "documents" in raw_results:
        docs = raw_results.get("documents", [[]])[0]
        metas = raw_results.get("metadatas", [[]])[0] if raw_results.get("metadatas") else []
        
        for idx, text in enumerate(docs):
            meta = metas[idx] if idx < len(metas) and metas[idx] else {}
            extracted.append({
                "title": meta.get("title", f"Article {idx + 1}"),
                "text": text
            })
    elif isinstance(raw_results, list):
        extracted = raw_results
    return extracted


def main():
    print("=== Testing News Intelligence RAG Pipeline ===")
    
    # 1. Initialize Ammu's components
    embedder = EmbeddingGenerator()
    chroma = ChromaManager()
    
    query = "What are the latest updates in technology?"
    print(f"\n1. Converting query to embedding and searching ChromaDB: '{query}'...")
    
    query_embedding = embedder.generate_embedding(query)
    raw_docs = chroma.search_articles(query_embedding=query_embedding, top_k=3)
    
    # Unpack raw Chroma dictionary into actual article objects
    retrieved_articles = extract_articles_from_chroma(raw_docs)
    print(f"   Successfully extracted {len(retrieved_articles)} articles from ChromaDB.")

    # 2. Initialize RAG Engine with Groq
    print("\n2. Initializing Groq LLM (Llama 3.3 70B)...")
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
    rag_engine = NewsGenerationEngine(llm_model=llm)

    # 3. Test Case A: High Trust Score (Normal Briefing)
    print("\n3. Generating Briefing (Trust Score: 8/10)...")
    briefing = rag_engine.generate_briefing(question=query, retrieved_articles=retrieved_articles, trust_score=8)
    print("\n--- FINAL BRIEFING ---")
    print(briefing)

    # 4. Test Case B: Low Trust Score (Triggers Warning)
    print("\n\n4. Generating Briefing with Warning (Mock Trust Score: 3/10)...")
    briefing_warning = rag_engine.generate_briefing(question=query, retrieved_articles=retrieved_articles, trust_score=3)
    print("\n--- FINAL BRIEFING (WITH WARNING) ---")
    print(briefing_warning)

if __name__ == "__main__":
    main()



#  To Test run
# python scripts/test_rag_pipeline.py