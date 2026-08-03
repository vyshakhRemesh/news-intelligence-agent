"""
BERTopic wrapper with model persistence and probability disabled.
"""
import logging
import os
from typing import List, Tuple, Optional

from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer
import numpy as np

logger = logging.getLogger(__name__)


class BERTopicModel:
    """
    BERTopic wrapper with:
    - Model save/load for stable topic IDs across runs
    - calculate_probabilities=False (memory efficient)
    - English stop-word removal
    """

    def __init__(self, model_path: str = "./models/bertopic"):
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        self.model_path = model_path
        self.model = None

    def _create_model(self) -> BERTopic:
        """Create a fresh BERTopic instance."""
        return BERTopic(
            embedding_model=self.embedding_model,
            vectorizer_model=CountVectorizer(stop_words="english"),
            calculate_probabilities=False,  # FIX: Memory efficient
            verbose=True,
            min_topic_size=5,
        )

    def fit(self, documents: List[str], embeddings: np.ndarray) -> Tuple[List[int], BERTopic]:
        """
        Train BERTopic on documents and embeddings.
        Saves model to disk for future transforms.
        """
        self.model = self._create_model()
        topics, _ = self.model.fit_transform(documents, embeddings)
        self._save_model()
        logger.info(f"BERTopic trained: {len(set(topics)) - (1 if -1 in topics else 0)} topics, {topics.count(-1)} outliers")
        return topics, self.model

    def transform(self, documents: List[str], embeddings: np.ndarray) -> List[int]:
        """
        Transform new documents using a pre-trained model.
        Loads from disk if not in memory.
        """
        if self.model is None:
            self._load_model()

        if self.model is None:
            logger.warning("No saved BERTopic model found. Call fit() first.")
            return [-1] * len(documents)

        topics, _ = self.model.transform(documents, embeddings)
        logger.info(f"BERTopic transform: {len(documents)} articles, {topics.count(-1)} outliers")
        return topics

    def get_topic_keywords(self, topic_id: int) -> List[Tuple[str, float]]:
        """Get keywords for a topic."""
        if self.model is None:
            self._load_model()
        if self.model is None:
            return []
        return self.model.get_topic(topic_id) or []

    def _save_model(self):
        """Save trained model to disk."""
        os.makedirs(os.path.dirname(self.model_path) or ".", exist_ok=True)
        self.model.save(self.model_path)
        logger.info(f"BERTopic model saved to {self.model_path}")

    def _load_model(self) -> bool:
        """Load model from disk. Returns True if successful."""
        if os.path.exists(self.model_path):
            try:
                self.model = BERTopic.load(self.model_path)
                logger.info(f"BERTopic model loaded from {self.model_path}")
                return True
            except Exception as e:
                logger.error(f"Failed to load BERTopic model: {e}")
        return False

    def retrain(self, documents: List[str], embeddings: np.ndarray) -> Tuple[List[int], BERTopic]:
        """Force retrain from scratch. Use weekly to capture emerging topics."""
        logger.info("Force retraining BERTopic from scratch...")
        if os.path.exists(self.model_path):
            import shutil
            shutil.rmtree(self.model_path)
            logger.info("Old model removed.")
        return self.fit(documents, embeddings)
