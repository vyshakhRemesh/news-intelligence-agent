"""
Source Preference Module

Checks whether the article is from the user's preferred news source.
"""


class SourcePreference:

    @staticmethod
    def calculate(article, user):

        source = getattr(article, "source_name", None)

        if source is None:
            return 50

        preferred = [
            s.lower()
            for s in user["preferred_sources"]
        ]

        if source.lower() in preferred:
            return 100

        return 60