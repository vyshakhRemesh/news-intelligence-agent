"""
Recommendation Service

Calculates recommendation scores and optionally
stores the results in PostgreSQL.
"""

from src.database.models import ArticleRecommendation
from src.recommendation.recommendation_engine import (
    RecommendationEngine,
)


class RecommendationService:

    def __init__(self, db=None):
        self.engine = RecommendationEngine()
        self.db = db

    def recommend(
        self,
        articles,
        user,
        save_results=False,
    ):
        ranked_articles = self.engine.rank_articles(
            articles,
            user,
        )

        if save_results:
            self._save_results(
                ranked_articles,
                user,
            )

        return ranked_articles

    def _save_results(
        self,
        ranked_articles,
        user,
    ):
        if self.db is None:
            raise ValueError(
                "A database session is required "
                "to save recommendation scores."
            )

        user_id = user.get("id")

        try:
            for item in ranked_articles:
                article = item["article"]
                scores = item["scores"]

                record = ArticleRecommendation(
                    article_id=article.id,
                    user_id=user_id,
                    trust_score=scores["trust_score"],
                    confidence_score=scores[
                        "confidence_score"
                    ],
                    freshness_score=scores[
                        "freshness_score"
                    ],
                    interest_score=scores[
                        "interest_score"
                    ],
                    source_preference_score=scores[
                        "source_preference_score"
                    ],
                    recommendation_score=scores[
                        "recommendation_score"
                    ],
                )

                self.db.add(record)

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise