import logging
from typing import Dict, Any

from src.contradiction.contradiction_engine import (
    ContradictionEngine,
)

logger = logging.getLogger(__name__)


class ContradictionService:
    """
    Public interface for contradiction detection.
    """

    def __init__(self):

        self.engine = ContradictionEngine()

    def analyse(
        self,
        text: str,
        top_k: int = 5,
        threshold: float = 0.70,
        max_similarity_distance: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Detect contradictory articles for the provided text.
        """

        contradictions = self.engine.detect_contradictions(
            query_text=text,
            top_k=top_k,
            contradiction_threshold=threshold,
            max_similarity_distance=max_similarity_distance,
        )

        return {
            "query": text.strip(),
            "contradiction_count": len(contradictions),
            "contradictions": contradictions,
        }
    def analyse_articles(
    self,
    articles: list,
    threshold: float = 0.70,
    ) -> dict:
        """
        Compare retrieved articles with each other and identify
        potentially contradictory pairs.
        """

        contradictions = []

        for first_index in range(len(articles)):
            for second_index in range(first_index + 1, len(articles)):
                first_article = articles[first_index]
                second_article = articles[second_index]

                first_text = self._extract_article_text(first_article)
                second_text = self._extract_article_text(second_article)

                if not first_text or not second_text:
                    continue

                prediction = self.engine.nli.predict(
                    first_text,
                    second_text,
                )

                scores = prediction.get("scores", {})
                contradiction_score = scores.get(
                    "contradiction",
                    0.0,
                )

                if contradiction_score >= threshold:
                    contradictions.append({
                        "article_1_index": first_index,
                        "article_2_index": second_index,
                        "article_1_title": self._extract_title(
                            first_article,
                            first_index,
                        ),
                        "article_2_title": self._extract_title(
                            second_article,
                            second_index,
                        ),
                        "contradiction_score": contradiction_score,
                        "entailment_score": scores.get(
                            "entailment",
                            0.0,
                        ),
                        "neutral_score": scores.get(
                            "neutral",
                            0.0,
                        ),
                    })

        contradictions.sort(
            key=lambda item: item["contradiction_score"],
            reverse=True,
        )

        return {
            "contradiction_count": len(contradictions),
            "contradictions": contradictions,
        }

    @staticmethod
    def _extract_article_text(article) -> str:
        if isinstance(article, str):
            return article.strip()

        if isinstance(article, dict):
            title = article.get("title", "") or ""
            description = article.get("description", "") or ""
            content = (
                article.get("text")
                or article.get("content")
                or article.get("summary")
                or ""
            )

            return f"{title}\n{description}\n{content}".strip()

        return str(article).strip()


    @staticmethod
    def _extract_title(article, index: int) -> str:
        if isinstance(article, dict):
            return article.get(
                "title",
                f"Article {index + 1}",
            )

        return f"Article {index + 1}"