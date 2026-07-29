"""
Source Preference Module

Checks whether the article is from the user's preferred news source.
"""


class SourcePreference:

    @staticmethod
    def calculate(article, user):

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
            return 50

        preferred_sources = user.get(
            "preferred_sources",
            [],
        )

        preferred = {
            item.strip().lower()
            for item in preferred_sources
            if item
        }

        normalised_source = source.strip().lower()

        if normalised_source in preferred:
            return 100

        return 60