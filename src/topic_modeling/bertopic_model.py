# src/topic_modeling/bertopic_model.py

import logging

from bertopic import BERTopic
from sklearn.feature_extraction.text import CountVectorizer

logger = logging.getLogger(__name__)


class BERTopicModel:

    def __init__(self):

        logger.info("Initializing BERTopic...")

        self.model = BERTopic(

            language="english",

            calculate_probabilities=True,

            min_topic_size=5,

            vectorizer_model=CountVectorizer(
                stop_words="english"
            ),

            verbose=True
        )

        logger.info("BERTopic initialized.")

    def fit(self, documents, embeddings):

        logger.info(
            f"Training BERTopic on {len(documents)} documents..."
        )

        topics, probabilities = self.model.fit_transform(
            documents,
            embeddings
        )

        logger.info("BERTopic training completed.")

        return topics, probabilities

    def get_topic_keywords(self, topic_id):

        return self.model.get_topic(topic_id)

    def get_topic_info(self):

        return self.model.get_topic_info()

    def save(self, path):

        self.model.save(path)

    def load(self, path):

        self.model = BERTopic.load(path)