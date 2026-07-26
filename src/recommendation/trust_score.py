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
        """
        Return the configured credibility score for one article.

        Supports both article objects and dictionaries.
        """

        if isinstance(article, dict):
            source = (
                article.get("source_name")
                or article.get("source")
            )
        else:
            source = getattr(article, "source_name", None)

            if source is None:
                source = getattr(article, "source", None)

        if not source:
            return DEFAULT_TRUST_SCORE

        return SOURCE_TRUST.get(
            source,
            DEFAULT_TRUST_SCORE,
        )