"""
Confidence Score

Calculates confidence independently from the enrichment quality score.

The score is based on:
- Article content completeness
- Language-detection confidence
- Availability of article metadata
- Extracted entities
"""


class ConfidenceScore:
    """Calculate an independent confidence score for an article."""

    @staticmethod
    def calculate(article) -> float:
        score = 0.0

        # -------------------------------------------------
        # 1. Content completeness: maximum 50 points
        # -------------------------------------------------

        title = str(
            getattr(article, "title", "") or ""
        ).strip()

        description = str(
            getattr(article, "description", "") or ""
        ).strip()

        content = str(
            getattr(article, "content", "") or ""
        ).strip()

        if title:
            score += 10

        if description:
            score += 15

        if content:
            score += 15

            # Give additional confidence when the article
            # contains a reasonable amount of content.
            word_count = len(content.split())

            if word_count >= 100:
                score += 5

            if word_count >= 300:
                score += 5

        # -------------------------------------------------
        # 2. Language confidence: maximum 20 points
        # -------------------------------------------------

        language_confidence = getattr(
            article,
            "language_confidence",
            0,
        ) or 0

        try:
            language_confidence = float(language_confidence)
        except (TypeError, ValueError):
            language_confidence = 0

        # Support values stored either as 0-1 or 0-100.
        if language_confidence <= 1:
            language_confidence *= 100

        language_confidence = max(
            0,
            min(100, language_confidence),
        )

        score += language_confidence * 0.20

        # -------------------------------------------------
        # 3. Metadata availability: maximum 20 points
        # -------------------------------------------------

        if getattr(article, "author", None):
            score += 5

        if getattr(article, "source_name", None):
            score += 5

        if getattr(article, "published_at", None):
            score += 5

        if getattr(article, "url", None):
            score += 5

        # -------------------------------------------------
        # 4. Entity extraction: maximum 10 points
        # -------------------------------------------------

        entities = getattr(article, "entities", None) or []

        if isinstance(entities, list):
            entity_count = len(entities)
        elif isinstance(entities, dict):
            entity_count = len(entities)
        else:
            entity_count = 0

        if entity_count >= 1:
            score += 5

        if entity_count >= 3:
            score += 5

        return round(
            max(0, min(100, score)),
            2,
        )