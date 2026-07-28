"""
Topic service with model persistence, outlier handling, and duplicate filtering.
"""
import logging
from typing import List, Dict, Any

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from src.database.models import RawArticles
from src.topic_modeling.bertopic_model import BERTopicModel
from src.semantic_representation.embedding_generator import EmbeddingGenerator
from src.database.connection import SessionLocal



logger = logging.getLogger(__name__)


class TopicService:
    """
    Manages BERTopic training and inference with:
    - Model persistence (train once, transform daily)
    - Outlier reassignment via embedding similarity
    - Duplicate filtering
    - Better topic labels (top-3 words)
    """

    def __init__(self, db: Session, model_path: str = "./models/bertopic"):
        self.db = db
        self.topic_model = BERTopicModel(model_path=model_path)
        self.embedder = EmbeddingGenerator()

    def load_articles(self) -> List[RawArticles]:
        """
        Load unprocessed articles that have cleaned content.
        Filters out duplicates to prevent topic inflation.
        """
        articles = (
            self.db.query(RawArticles)
            .filter(RawArticles.cleaned_content.isnot(None))
            .filter(RawArticles.topic_id.is_(None))
            .filter(RawArticles.is_duplicate == False)  # FIX: Skip duplicates
            .all()
        )
        logger.info(f"Loaded {len(articles)} unprocessed, non-duplicate articles for topic modeling")
        return articles

    def train(self, articles: List[RawArticles]) -> None:
        """
        Train or transform articles using BERTopic.

        Logic:
        1. If saved model exists: transform new articles only (stable topic IDs)
        2. If no model: fit on current batch (first run)
        3. Reassign outliers to nearest topic via embedding similarity
        """
        if not articles:
            logger.info("No articles to process")
            return

        documents = [article.cleaned_content for article in articles]
        embeddings = self.embedder.generate_embeddings(documents)

        # Check if we have a saved model
        model_exists = self.topic_model._load_model()

        if model_exists:
            # Transform only new articles with existing model
            logger.info("Using saved BERTopic model for transform")
            topics = self.topic_model.transform(documents, embeddings)
        else:
            # First run: fit on all available articles
            logger.info("No saved model found. Training BERTopic from scratch...")
            topics, _ = self.topic_model.fit(documents, embeddings)

        # FIX: Reassign outliers (-1) to nearest topic
        topics = self._reassign_outliers(topics, embeddings)

        self.save_topics(articles, topics)
        logger.info(f"Topic modeling complete: {len(set(topics))} topics assigned")

    def _reassign_outliers(self, topics: List[int], embeddings: np.ndarray) -> List[int]:
        """
        Reassign outlier articles (topic == -1) to their nearest topic
        using cosine similarity between article embeddings and topic centroids.
        """
        topics = list(topics)
        outlier_indices = [i for i, t in enumerate(topics) if t == -1]

        if not outlier_indices:
            return topics

        # Build topic centroids from non-outlier assignments
        unique_topics = list(set(t for t in topics if t != -1))
        if not unique_topics:
            logger.warning("All articles are outliers — cannot reassign")
            return topics

        topic_centroids = {}
        for topic_id in unique_topics:
            topic_mask = [i for i, t in enumerate(topics) if t == topic_id]
            if topic_mask:
                topic_centroids[topic_id] = np.mean(embeddings[topic_mask], axis=0)

        if not topic_centroids:
            return topics

        # Reassign each outlier to nearest topic centroid
        centroid_topics = list(topic_centroids.keys())
        centroid_matrix = np.array([topic_centroids[t] for t in centroid_topics])

        for idx in outlier_indices:
            article_embedding = embeddings[idx].reshape(1, -1)
            similarities = cosine_similarity(article_embedding, centroid_matrix)[0]
            best_topic = centroid_topics[int(np.argmax(similarities))]
            topics[idx] = best_topic
            logger.debug(f"Reassigned outlier article {idx} to topic {best_topic}")

        logger.info(f"Reassigned {len(outlier_indices)} outliers to nearest topics")
        return topics

    def save_topics(self, articles: List[RawArticles], topics: List[int]) -> None:
        """Save topic assignments to database with better labels."""
        for article, topic in zip(articles, topics):
            topic_keywords = self.topic_model.get_topic_keywords(topic)

            # FIX: Use top 3 words for readable label instead of just words[0]
            words = [word for word, score in topic_keywords]
            primary_topic = " ".join(words[:3]) if words else f"topic_{topic}"

            article.topic_id = int(topic)
            article.primary_topic = primary_topic
            article.topics = words[:10]  # Store top 10 keywords

        self.db.commit()
        logger.info(f"Saved topics for {len(articles)} articles")

    def retrain(self) -> None:
        """Force retrain from scratch. Call weekly to capture emerging topics."""
        articles = (
            self.db.query(RawArticles)
            .filter(RawArticles.cleaned_content.isnot(None))
            .filter(RawArticles.is_duplicate == False)
            .order_by(RawArticles.published_at.desc())
            .limit(500)  # Use last 500 articles for retraining
            .all()
        )

        if len(articles) < 10:
            logger.warning("Not enough articles for retraining (need 10+)")
            return

        documents = [a.cleaned_content for a in articles]
        embeddings = self.embedder.generate_embeddings(documents)

        topics, _ = self.topic_model.retrain(documents, embeddings)
        topics = self._reassign_outliers(topics, embeddings)
        self.save_topics(articles, topics)
        logger.info("BERTopic retrained from scratch on recent articles")

    def run(self) -> None:
        """Main entry point."""
        articles = self.load_articles()
        if articles:
            self.train(articles)
        else:
            logger.info("No new articles for topic modeling")
