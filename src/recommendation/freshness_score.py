"""
Freshness Score

Calculates article freshness using its age in hours.
Newly published articles receive higher scores.
"""

from datetime import datetime, timezone


class FreshnessScore:

    @staticmethod
    def calculate(article) -> float:

        published = getattr(article, "published_at", None)

        if published is None:
            return 50.0

        # Convert ISO datetime string to datetime
        if isinstance(published, str):
            try:
                published = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                )
            except ValueError:
                return 50.0

        # Make timezone-naive dates UTC-aware
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)

        age_seconds = (now - published).total_seconds()

        # Protect against future publication timestamps
        if age_seconds < 0:
            age_seconds = 0

        age_hours = age_seconds / 3600

        if age_hours <= 2:
            return 100.0

        elif age_hours <= 4:
            return 98.0

        elif age_hours <= 6:
            return 96.0

        elif age_hours <= 8:
            return 94.0

        elif age_hours <= 10:
            return 92.0

        elif age_hours <= 12:
            return 90.0

        elif age_hours <= 24:
            return 85.0

        elif age_hours <= 48:
            return 75.0

        elif age_hours <= 72:
            return 65.0

        elif age_hours <= 96:
            return 55.0

        elif age_hours <= 120:
            return 45.0

        elif age_hours <= 144:
            return 35.0

        elif age_hours <= 168:  # One week
            return 25.0

        else:
            return 10.0