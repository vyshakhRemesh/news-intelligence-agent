"""
Trust Score Module

Calculates trust score based on the credibility of the news source.

Author: Recommendation Team
"""


from src.config_recomm.trust_sources import (
    SOURCE_TRUST,
    DEFAULT_TRUST_SCORE
    )

class TrustScore:


    @staticmethod
    def calculate(article):

        source = getattr(article, "source_name", None)

        if source is None:
            return DEFAULT_TRUST_SCORE

        return SOURCE_TRUST.get(
        source,
        DEFAULT_TRUST_SCORE
        )