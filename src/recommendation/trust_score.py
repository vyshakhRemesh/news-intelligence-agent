"""
Trust Score Module

Calculates trust score based on the credibility of the news source.

Author: Recommendation Team
"""

from src.recommendation.trust_sources import (
    SOURCE_TRUST,
    DEFAULT_TRUST_SCORE,
)


class TrustScore:

    @staticmethod
    def calculate(article):

        if isinstance(article, dict):
            source = (
                article.get("source_name")
                or article.get("source")
            )
        else:
            source = (
                getattr(article, "source_name", None)
                or getattr(article, "source", None)
            )

        if not source:
            return DEFAULT_TRUST_SCORE

        normalised_source = source.strip().lower()

        return SOURCE_TRUST.get(
            normalised_source,
            DEFAULT_TRUST_SCORE,
        )