"""
Freshness Score

Calculates how recent a news article is.
"""

from datetime import datetime


class FreshnessScore:

    @staticmethod
    def calculate(article):

        published = getattr(article, "published_at", None)

        if published is None:
            return 50
        if isinstance(published, str):
            published = datetime.fromisoformat(published)

        days = (datetime.utcnow() - published).days

        if days == 0:
            return 100

        elif days == 1:
            return 95

        elif days <= 3:
            return 90

        elif days <= 7:
            return 80

        elif days <= 14:
            return 65

        elif days <= 30:
            return 50

        else:
            return 30