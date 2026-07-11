import logging
from src.semantic_representation.embedding_generator import EmbeddingGenerator
from src.topic_modeling.bertopic_model import BERTopicModel
from src.database.connection import SessionLocal
from src.database.models import RawArticles

logger = logging.getLogger(__name__)


class TopicService:

    def __init__(self):

        self.db = SessionLocal()
        self.embedding_generator = EmbeddingGenerator()
        self.topic_model = BERTopicModel()

    def load_articles(self):

        logger.info("Loading articles...")

        articles = (
            self.db.query(RawArticles)
            .filter(
                RawArticles.cleaned_content.isnot(None)
            )
            .all()
        )

        logger.info(f"Loaded {len(articles)} articles")

        return articles
    
    def prepare_documents(self, articles):

        logger.info("Preparing documents...")

        documents = []

        valid_articles = []

        for article in articles:

            if article.cleaned_content:

                documents.append(
                    article.cleaned_content
                )

                valid_articles.append(
                    article
                )

        logger.info(
            f"Prepared {len(documents)} documents"
        )

        return documents, valid_articles
    
    def generate_embeddings(self, documents):

        logger.info("Generating embeddings...")

        embeddings = self.embedding_generator.generate_embeddings(
            documents
        )

        logger.info(
            f"Generated {embeddings.shape[0]} embeddings"
        )

        return embeddings
    
    def train(self, documents, embeddings):

        logger.info("=" * 60)
        logger.info("Running BERTopic...")
        logger.info("=" * 60)


        topics, probabilities = self.topic_model.fit(
            documents,
            embeddings
        )

        logger.info("BERTopic completed successfully.")

        return topics, probabilities
    
    def save_topics(
    self,
    articles,
    topics
):
        """
        Save BERTopic results back to PostgreSQL.
        """

        logger.info("=" * 60)
        logger.info("Saving BERTopic results...")
        logger.info("=" * 60)

        updated = 0

        for article, topic in zip(articles, topics):

            # ----------------------------
            # Handle Outliers
            # ----------------------------
            if topic == -1:

                article.topic_id = -1
                article.primary_topic = "Outlier"
                article.topics = []

                updated += 1
                continue

            # ----------------------------
            # Topic ID
            # ----------------------------
            article.topic_id = int(topic)

            # ----------------------------
            # Topic Keywords
            # ----------------------------
            topic_keywords = self.topic_model.get_topic_keywords(topic)

            if topic_keywords:

                words = [
                    word
                    for word, score in topic_keywords
                ]

                article.topics = words

                article.primary_topic = words[0]

            else:

                article.topics = []

                article.primary_topic = "Unknown"

            updated += 1

        try:

            self.db.commit()

            logger.info(
                f"Successfully updated {updated} articles."
            )

        except Exception as e:

            self.db.rollback()

            logger.error(f"Database commit failed: {e}")

            raise

        return updated
    
    def run(self):
        """
        Complete BERTopic Pipeline
        """

        logger.info("=" * 70)
        logger.info("STARTING TOPIC MODELING PIPELINE")
        logger.info("=" * 70)

        # ----------------------------------------
        # Load Articles
        # ----------------------------------------
        articles = (
        self.db.query(RawArticles)
        .filter(
            RawArticles.cleaned_content.isnot(None),
            RawArticles.topic_id.is_(None)
        )
        .all()
    )

        # ----------------------------------------
        # Prepare Documents
        # ----------------------------------------
        documents, valid_articles = self.prepare_documents(
            articles
        )

        if not documents:
            logger.warning("No valid documents found.")
            return

        # ----------------------------------------
        # Generate Embeddings
        # ----------------------------------------
        embeddings = self.generate_embeddings(
            documents
        )

        # ----------------------------------------
        # BERTopic
        # ----------------------------------------
        topics, probabilities = self.train(
            documents,
            embeddings
        )

        # ----------------------------------------
        # Save
        # ----------------------------------------
        updated = self.save_topics(
            valid_articles,
            topics
        )

        logger.info("=" * 70)
        logger.info(
            f"BERTopic Pipeline Completed. Updated {updated} Articles."
        )   
        logger.info("=" * 70)