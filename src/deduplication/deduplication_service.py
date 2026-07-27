import logging

from src.database.models import (
    RawArticles,
    ArticleRecommendation,
    ArticleContradiction,
)
from src.contradiction.contradiction_service import (
    ContradictionService,
)
from sklearn.metrics.pairwise import cosine_similarity
logger = logging.getLogger(__name__)


class DeduplicationService:
    """
    Handles semantic article deduplication after
    recommendation and contradiction analysis.
    """

    def __init__(self, db, chroma_manager):
        if db is None:
            raise ValueError(
                "A database session is required "
                "for deduplication."
            )

        if chroma_manager is None:
            raise ValueError(
                "ChromaManager is required "
                "for semantic deduplication."
            )

        self.db = db
        self.chroma_manager = chroma_manager
        self.contradiction_service = ContradictionService(
            db=self.db
        )
    def _get_recommendation_score(
        self,
        article_id: int,
    ) -> float:
        """
        Returns the latest recommendation score
        for an article.
        """

        recommendation = (
            self.db.query(ArticleRecommendation)
            .filter(
                ArticleRecommendation.article_id == article_id
            )
            .order_by(
                ArticleRecommendation.calculated_at.desc()
            )
            .first()
        )

        if recommendation is None:
            return 0.0

        return recommendation.recommendation_score


    def _calculate_similarity(
        self,
        embedding1,
        embedding2,
    ) -> float:
        """
        Calculates cosine similarity between
        two article embeddings.
        """

        if embedding1 is None or embedding2 is None:
            return 0.0

        score = cosine_similarity(
            [embedding1],
            [embedding2],
        )[0][0]

        return float(score)

    def _are_contradictory(
        self,
        article1: RawArticles,
        article2: RawArticles,
        threshold: float = 0.50,
    ) -> bool:
        """
        Check an existing contradiction record first.

        When no record exists, run contradiction analysis
        for this exact article pair.
        """

        first_id, second_id = sorted(
            [article1.id, article2.id]
        )

        existing_contradiction = (
            self.db.query(ArticleContradiction)
            .filter(
                ArticleContradiction.article_1_id
                == first_id,
                ArticleContradiction.article_2_id
                == second_id,
            )
            .first()
        )

        if existing_contradiction is not None:
            return True

        return (
            self.contradiction_service
            .are_articles_contradictory(
                article1=article1,
                article2=article2,
                threshold=threshold,
            )
        )

    def _find_similar_articles(
        self,
        article_id: int,
        top_k: int = 5,
    ) -> list:
        """
        Finds the most semantically similar articles
        to the supplied article.

        The current article itself is excluded.
        """

        stored_article = self.chroma_manager.get_article(
            article_id
        )

        if stored_article is None:
            logger.warning(
                "Article %s was not found in ChromaDB.",
                article_id,
            )
            return []

        query_embedding = stored_article.get("embedding")

        if query_embedding is None:
            logger.warning(
                "Embedding missing for article %s.",
                article_id,
            )
            return []

        article_count = self.chroma_manager.count_articles()

        if article_count <= 1:
            return []

        number_of_results = min(
            top_k + 1,
            article_count,
        )

        results = self.chroma_manager.search_articles(
            query_embedding=query_embedding,
            top_k=number_of_results,
        )

        result_ids = results.get("ids", [[]])[0] or []

        similar_articles = []

        for candidate_id in result_ids:
            try:
                candidate_id = int(candidate_id)
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid article ID returned by ChromaDB: %s",
                    candidate_id,
                )
                continue

            # ChromaDB normally returns the queried article
            # as the first result, so exclude it.
            if candidate_id == article_id:
                continue

            candidate = self.chroma_manager.get_article(
                candidate_id
            )

            if candidate is None:
                continue

            similarity = self._calculate_similarity(
                query_embedding,
                candidate.get("embedding"),
            )

            similar_articles.append(
                {
                    "article_id": candidate_id,
                    "similarity": similarity,
                }
            )

        similar_articles.sort(
            key=lambda item: item["similarity"],
            reverse=True,
        )

        return similar_articles[:top_k]

    def _choose_article_to_keep(
        self,
        article1: RawArticles,
        article2: RawArticles,
    ):
        """
        Chooses which article should be retained based on
        the latest recommendation score.

        Returns:
            (article_to_keep, article_to_mark_duplicate)
        """

        article1_score = self._get_recommendation_score(
            article1.id
        )
        article2_score = self._get_recommendation_score(
            article2.id
        )

        if article1_score > article2_score:
            return article1, article2

        if article2_score > article1_score:
            return article2, article1

        # Tie-breaker:
        # keep the newer article when recommendation
        # scores are equal.
        article1_date = article1.published_at
        article2_date = article2.published_at

        if (
            article1_date is not None
            and article2_date is not None
            and article2_date > article1_date
        ):
            return article2, article1

        # Final stable tie-breaker:
        # keep the article with the lower database ID.
        if article1.id <= article2.id:
            return article1, article2

        return article2, article1

    def preview_duplicates(
        self,
        similarity_threshold: float = 0.90,
        top_k: int = 5,
    ) -> list:
        """
        Finds semantic duplicate candidates without
        changing any database records.
        """

        articles = (
            self.db.query(RawArticles)
            .filter(
                RawArticles.preprocessing_status == "completed",
                RawArticles.is_duplicate == False,
            )
            .all()
        )

        article_map = {
            article.id: article
            for article in articles
        }

        checked_pairs = set()
        duplicate_candidates = []

        for article in articles:

            similar_articles = self._find_similar_articles(
                article_id=article.id,
                top_k=top_k,
            )

            for candidate_data in similar_articles:

                candidate_id = candidate_data["article_id"]
                similarity = candidate_data["similarity"]

                if similarity < similarity_threshold:
                    continue

                if candidate_id not in article_map:
                    continue

                pair = tuple(
                    sorted([article.id, candidate_id])
                )

                # Avoid checking A-B and then B-A.
                if pair in checked_pairs:
                    continue

                checked_pairs.add(pair)

                candidate_article = article_map[candidate_id]

                # Contradictory articles must both remain.
                if self._are_contradictory(
                    article,
                    candidate_article,
                ):
                    logger.info(
                        "Keeping articles %s and %s because "
                        "they are contradictory.",
                        article.id,
                        candidate_article.id,
                    )
                    continue

                article_to_keep, article_to_remove = (
                    self._choose_article_to_keep(
                        article,
                        candidate_article,
                    )
                )

                result = {
                    "keep_article_id": article_to_keep.id,
                    "duplicate_article_id": article_to_remove.id,
                    "similarity": similarity,
                    "keep_score": self._get_recommendation_score(
                        article_to_keep.id
                    ),
                    "duplicate_score":
                        self._get_recommendation_score(
                            article_to_remove.id
                        ),
                }

                duplicate_candidates.append(result)

                logger.info(
                    "Duplicate candidate: keep=%s, duplicate=%s, "
                    "similarity=%.4f",
                    article_to_keep.id,
                    article_to_remove.id,
                    similarity,
                )

        return duplicate_candidates

    def apply_duplicates(
        self,
        duplicate_candidates,
    ):
        """
        Marks semantic duplicates in PostgreSQL.

        The article with the better recommendation score
        is kept. The other article is marked as a duplicate.
        """

        updated = 0

        for candidate in duplicate_candidates:

            keep_id = candidate["keep_article_id"]
            duplicate_id = candidate["duplicate_article_id"]

            duplicate_article = (
                self.db.query(RawArticles)
                .filter(
                    RawArticles.id == duplicate_id
                )
                .first()
            )

            if duplicate_article is None:
                continue

            duplicate_article.is_duplicate = True
            duplicate_article.duplicate_of_id = keep_id

            updated += 1

        self.db.commit()

        logger.info(
            "Marked %d duplicate articles.",
            updated,
        )

        return updated