import logging
from typing import Dict, Any
from datetime import datetime, timezone

from src.database.models import (
    RawArticles,
    ArticleContradiction,
)
from src.contradiction.contradiction_engine import (
    ContradictionEngine,
)

logger = logging.getLogger(__name__)


class ContradictionService:
    """
    Public interface for contradiction detection.
    """

    def __init__(self,db=None):

        self.engine = ContradictionEngine()
        self.db = db

    def are_articles_contradictory(
        self,
        article1: RawArticles,
        article2: RawArticles,
        threshold: float = 0.50,
    ) -> bool:
        """
        Compare one specific pair of articles using the NLI model.

        Returns True when the contradiction score reaches
        the configured threshold.
        """

        first_text = (
            article1.cleaned_content
            or article1.content
            or article1.description
            or ""
        )

        second_text = (
            article2.cleaned_content
            or article2.content
            or article2.description
            or ""
        )

        first_text = (
            f"{article1.title or ''}\n{first_text}"
        ).strip()

        second_text = (
            f"{article2.title or ''}\n{second_text}"
        ).strip()

        if not first_text or not second_text:
            logger.warning(
                "Cannot check contradiction for articles %s and %s "
                "because article text is missing.",
                article1.id,
                article2.id,
            )
            return False

        prediction = self.engine.nli.predict(
            first_text,
            second_text,
        )

        scores = prediction.get("scores", {})

        contradiction_score = float(
            scores.get("contradiction", 0.0)
        )

        entailment_score = float(
            scores.get("entailment", 0.0)
        )

        neutral_score = float(
            scores.get("neutral", 0.0)
        )

        is_contradiction = (
            contradiction_score >= threshold
        )

        logger.info(
            "Contradiction check: article1=%s, article2=%s, "
            "score=%.4f, threshold=%.2f, result=%s",
            article1.id,
            article2.id,
            contradiction_score,
            threshold,
            is_contradiction,
        )

        if is_contradiction:
            self._save_results(
                contradictions=[
                    {
                        "article_1_id": article1.id,
                        "article_2_id": article2.id,
                        "contradiction_score":
                            contradiction_score,
                        "entailment_score":
                            entailment_score,
                        "neutral_score":
                            neutral_score,
                    }
                ],
                threshold=threshold,
            )

        return is_contradiction

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
        threshold: float = 0.50,
        save_results: bool = False,
    ) -> dict:
        """
        Compare retrieved articles pair by pair.

        When save_results is True, detected contradictions
        are also stored in PostgreSQL.
        """

        contradictions = []

        for first_index in range(len(articles)):
            for second_index in range(
                first_index + 1,
                len(articles),
            ):
                first_article = articles[first_index]
                second_article = articles[second_index]

                first_text = self._extract_article_text(
                    first_article
                )
                second_text = self._extract_article_text(
                    second_article
                )

                if not first_text or not second_text:
                    continue

                prediction = self.engine.nli.predict(
                    first_text,
                    second_text,
                )

                scores = prediction.get("scores", {})

                contradiction_score = float(
                    scores.get("contradiction", 0.0)
                )

                if contradiction_score < threshold:
                    continue

                contradiction = {
                    "article_1_id": self._extract_article_id(
                        first_article
                    ),
                    "article_2_id": self._extract_article_id(
                        second_article
                    ),
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
                    "entailment_score": float(
                        scores.get("entailment", 0.0)
                    ),
                    "neutral_score": float(
                        scores.get("neutral", 0.0)
                    ),
                }

                contradictions.append(contradiction)

        contradictions.sort(
            key=lambda item: item["contradiction_score"],
            reverse=True,
        )

        if save_results:
            self._save_results(
                contradictions=contradictions,
                threshold=threshold,
            )

        return {
            "contradiction_count": len(contradictions),
            "contradictions": contradictions,
        }


    def analyse_against_most_trusted(
        self,
        articles: list,
        threshold: float = 0.50,
        save_results: bool = False,
    ) -> dict:
        """
        Select the article with the highest trust score and
        compare it with every other retrieved article.
        """

        if len(articles) < 2:
            return {
                "reference_article": None,
                "comparison_count": 0,
                "contradiction_count": 0,
                "comparisons": [],
            }

        # Select the highest-trust article.
        reference_index = max(
            range(len(articles)),
            key=lambda index: self._extract_trust_score(
                articles[index]
            ),
        )

        reference_article = articles[reference_index]

        reference_text = self._extract_article_text(
            reference_article
        )

        reference_id = self._extract_article_id(
            reference_article
        )

        reference_title = self._extract_title(
            reference_article,
            reference_index,
        )

        reference_trust_score = self._extract_trust_score(
            reference_article
        )

        comparisons = []
        contradictions_to_save = []

        for compared_index, compared_article in enumerate(
            articles
        ):
            # Do not compare the reference article with itself.
            if compared_index == reference_index:
                continue

            compared_text = self._extract_article_text(
                compared_article
            )

            if not reference_text or not compared_text:
                logger.warning(
                    "Skipping comparison because article text "
                    "is missing."
                )
                continue

            prediction = self.engine.nli.predict(
                reference_text,
                compared_text,
            )

            scores = prediction.get("scores", {})

            contradiction_score = float(
                scores.get("contradiction", 0.0)
            )

            entailment_score = float(
                scores.get("entailment", 0.0)
            )

            neutral_score = float(
                scores.get("neutral", 0.0)
            )

            is_contradiction = (
                contradiction_score >= threshold
            )

            compared_id = self._extract_article_id(
                compared_article
            )

            compared_title = self._extract_title(
                compared_article,
                compared_index,
            )

            compared_trust_score = (
                self._extract_trust_score(
                    compared_article
                )
            )

            comparison = {
                "reference_article_id": reference_id,
                "reference_article_title": reference_title,
                "reference_trust_score": (
                    reference_trust_score
                ),
                "compared_article_id": compared_id,
                "compared_article_title": compared_title,
                "compared_trust_score": (
                    compared_trust_score
                ),
                "contradiction_score": round(
                    contradiction_score,
                    4,
                ),
                "entailment_score": round(
                    entailment_score,
                    4,
                ),
                "neutral_score": round(
                    neutral_score,
                    4,
                ),
                "threshold": threshold,
                "is_contradiction": is_contradiction,
            }

            comparisons.append(comparison)

            # Existing contradiction table stores only detected
            # contradictions above the threshold.
            if is_contradiction:
                contradictions_to_save.append({
                    "article_1_id": reference_id,
                    "article_2_id": compared_id,
                    "contradiction_score": (
                        contradiction_score
                    ),
                    "entailment_score": entailment_score,
                    "neutral_score": neutral_score,
                })

        comparisons.sort(
            key=lambda item: item["contradiction_score"],
            reverse=True,
        )

        if save_results:
            self._save_results(
                contradictions=contradictions_to_save,
                threshold=threshold,
            )

        return {
            "reference_article": {
                "article_id": reference_id,
                "title": reference_title,
                "trust_score": reference_trust_score,
            },
            "comparison_count": len(comparisons),
            "contradiction_count": sum(
                1
                for comparison in comparisons
                if comparison["is_contradiction"]
            ),
            "comparisons": comparisons,
        }
    @staticmethod
    def _extract_title(article, index: int) -> str:
        if isinstance(article, dict):
            title = article.get("title")

            if title:
                return str(title).strip()

        return f"Article {index + 1}"

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

    def _extract_article_id(article):
        if not isinstance(article, dict):
            return None

        article_id = article.get("article_id")

        if article_id is None:
            return None

        try:
            return int(article_id)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _extract_trust_score(article) -> float:
        if not isinstance(article, dict):
            return 0.0

        trust_score = article.get("trust_score", 0)

        try:
            return float(trust_score)
        except (TypeError, ValueError):
            return 0.0

    def _save_results(
        self,
        contradictions: list,
        threshold: float,
    ):
        if self.db is None:
            raise ValueError(
                "A database session is required to save "
                "contradiction results."
            )

        try:
            saved_count = 0

            for result in contradictions:
                article_1_id = result.get("article_1_id")
                article_2_id = result.get("article_2_id")

                if article_1_id is None or article_2_id is None:
                    logger.warning(
                        "Skipping contradiction because an "
                        "article ID is missing."
                    )
                    continue

                # Always store smaller ID first so that:
                # (10, 20) and (20, 10) are treated as one pair.
                first_id, second_id = sorted(
                    [article_1_id, article_2_id]
                )

                existing = (
                    self.db.query(ArticleContradiction)
                    .filter(
                        ArticleContradiction.article_1_id
                        == first_id,
                        ArticleContradiction.article_2_id
                        == second_id,
                    )
                    .first()
                )

                if existing:
                    existing.contradiction_score = result[
                        "contradiction_score"
                    ]
                    existing.entailment_score = result[
                        "entailment_score"
                    ]
                    existing.neutral_score = result[
                        "neutral_score"
                    ]
                    existing.threshold_used = threshold
                    existing.detected_at = datetime.now(
                        timezone.utc
                    )

                else:
                    record = ArticleContradiction(
                        article_1_id=first_id,
                        article_2_id=second_id,
                        contradiction_score=result[
                            "contradiction_score"
                        ],
                        entailment_score=result[
                            "entailment_score"
                        ],
                        neutral_score=result[
                            "neutral_score"
                        ],
                        threshold_used=threshold,
                    )

                    self.db.add(record)

                saved_count += 1

            self.db.commit()

            logger.info(
                "Saved or updated %d contradiction records.",
                saved_count,
            )

        except Exception:
            self.db.rollback()

            logger.exception(
                "Failed to save contradiction results."
            )

            raise