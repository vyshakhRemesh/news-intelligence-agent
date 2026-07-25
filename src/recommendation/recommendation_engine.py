"""
Recommendation Engine

Combines all recommendation factors and produces a
Personalized Recommendation Score.

Author: Recommendation Module
"""

from src.recommendation.trust_score import TrustScore
from src.recommendation.freshness_score import FreshnessScore
from src.recommendation.user_interest import UserInterest
from src.recommendation.source_preference import SourcePreference
from src.config_recomm.recommendation_config import (
    TRUST_WEIGHT,
    CONFIDENCE_WEIGHT,
    FRESHNESS_WEIGHT,
    INTEREST_WEIGHT,
    SOURCE_WEIGHT
    )

class RecommendationEngine:

    def calculate_score(self, article, user):

        # --------------------------
        # Individual Scores
        # --------------------------

        trust = TrustScore.calculate(article)

        freshness = FreshnessScore.calculate(article)

        # quality_score is already calculated by DataEnricher
        confidence = getattr(article, "quality_score", 50) or 50

        interest = UserInterest.calculate(article, user)

        source_preference = SourcePreference.calculate(article, user)

        # --------------------------
        # Final Recommendation Score
        # --------------------------

        recommendation_score = (

            trust * TRUST_WEIGHT +

            confidence * CONFIDENCE_WEIGHT +

            freshness * FRESHNESS_WEIGHT +

            interest * INTEREST_WEIGHT +

            source_preference * SOURCE_WEIGHT

        )

        return {

            "trust_score": round(trust,2),

            "freshness_score": round(freshness,2),

            "confidence_score": round(confidence,2),

            "interest_score": round(interest,2),

            "source_preference_score": round(source_preference,2),

            "recommendation_score": round(recommendation_score,2)

        }

    def rank_articles(self, articles, user):

        ranked_articles = []

        for article in articles:

            scores = self.calculate_score(article, user)

            ranked_articles.append({

            "title": getattr(article, "title", "Untitled"),

            "article": article,

            "scores": scores

            })

        ranked_articles.sort(

            key=lambda x: x["scores"]["recommendation_score"],

            reverse=True

        )

        return ranked_articles