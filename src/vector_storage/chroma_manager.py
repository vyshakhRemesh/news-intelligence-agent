import chromadb
import logging
from chromadb.config import Settings
logger = logging.getLogger(__name__)


class ChromaManager:

    def __init__(self):

        logger.info("Initializing ChromaDB...")

        self.client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=Settings(
                anonymized_telemetry=False
            )
        )

        self.collection = self.client.get_or_create_collection(
            name="news_articles"
        )

        logger.info("ChromaDB initialized successfully.")

    # ---------------- Store Article ----------------
    def store_article(
            self,
            article_id,
            text,
            embedding,
            metadata=None):
        
        article_id = str(article_id)

        existing = self.collection.get(ids=[article_id])

        if existing["ids"]:
                logger.info(f"Article {article_id} already exists in ChromaDB.")
                return False

        self.collection.add(
            ids=[str(article_id)],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata or {}]
        )

        logger.info(f"Stored article {article_id}")
        return True

    # ---------------- Search Articles ----------------
    def search_articles(
            self,
            query_embedding,
            top_k=5):

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )

        return results
            # ----------------- Helper method to search articles as text ----------------
    def search_by_text(self, query_text: str, top_k: int = 3, embedder=None):
        """
        Helper method to generate an embedding from text and query articles.
        """
        if embedder is None:
            from src.semantic_representation.embedding_generator import EmbeddingGenerator
            embedder = EmbeddingGenerator()
            
        embedding = embedder.generate_embedding(query_text)
        return self.search_articles(query_embedding=embedding, top_k=top_k)

    def get_article(self, article_id):
        """
        Returns the stored ChromaDB record for an article.
        """

        result = self.collection.get(
            ids=[str(article_id)],
            include=[
                "documents",
                "embeddings",
                "metadatas",
            ],
        )

        if not result["ids"]:
            return None

        return {
            "id": result["ids"][0],
            "document": result["documents"][0],
            "embedding": result["embeddings"][0],
            "metadata": result["metadatas"][0],
        }
    # ---------------- Count Articles ----------------
    def count_articles(self):

        return self.collection.count()


# ---------------- TESTING CODE ----------------
if __name__ == "__main__":

    db = ChromaManager()

    sample_embedding = [0.1] * 384

    db.store_article(
        article_id="1",
        text="Google launches Gemini AI.",
        embedding=sample_embedding,
        metadata={
            "source": "NewsAPI",
            "category": "Technology"
        }
    )

    print("Article stored successfully!")

    print("Total Articles:", db.count_articles())
# if __name__ == "__main__":

#     db = ChromaManager()

#     print("ChromaDB initialized successfully!")