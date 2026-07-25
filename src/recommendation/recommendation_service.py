"""
Recommendation Service

Acts as a bridge between ChromaDB search
and Recommendation Engine.
"""

from src.recommendation.recommendation_engine import RecommendationEngine


class RecommendationService:

    def __init__(self):

        self.engine = RecommendationEngine()

    def recommend(self, articles, user):

        ranked_articles = self.engine.rank_articles(
            articles,
            user
        )

        return ranked_articles