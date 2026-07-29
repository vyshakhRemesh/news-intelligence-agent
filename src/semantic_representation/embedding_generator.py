from sentence_transformers import SentenceTransformer
import numpy as np
import logging

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Handles embedding generation for the entire project.

    generate_embedding(text)
        -> Returns a Python list (used by ChromaDB)

    generate_embeddings(documents)
        -> Returns a NumPy array (used by BERTopic)
    """

    def __init__(self):

        logger.info("Loading MiniLM model...")

        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    # =====================================================
    # SINGLE ARTICLE (Used by ChromaDB)
    # =====================================================
    def generate_embedding(self, text):

        if not text:
            return None

        embedding = self.model.encode(
            text,
            convert_to_numpy=True
        )

        # Keep this as LIST so existing ChromaDB code
        # does not break.
        return embedding.tolist()

    # =====================================================
    # MULTIPLE ARTICLES (Used by BERTopic)
    # =====================================================
    def generate_embeddings(self, documents):

        if not documents:
            return np.array([])

        logger.info(
            f"Generating embeddings for {len(documents)} documents..."
        )

        embeddings = self.model.encode(
            documents,
            convert_to_numpy=True,
            show_progress_bar=True
        )

        logger.info("Batch embedding generation completed.")

        return embeddings