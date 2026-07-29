import logging
from typing import List, Dict, Any

from src.vector_storage.chroma_manager import ChromaManager
from src.semantic_representation.embedding_generator import EmbeddingGenerator
from src.contradiction.nli_model import NLIModel

logger = logging.getLogger(__name__)


class ContradictionEngine:
    """
    Retrieves semantically similar articles from ChromaDB and
    checks whether any of them contradict the input text.
    """

    def __init__(self):

        self.embedder = EmbeddingGenerator()
        self.chroma = ChromaManager()
        self.nli = NLIModel()

    def detect_contradictions(
        self,
        query_text: str,
        top_k: int = 5,
        contradiction_threshold: float = 0.70,
        max_similarity_distance: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve semantically related articles and return only genuine
        contradiction candidates.

        Articles with a ChromaDB distance greater than
        max_similarity_distance are ignored before NLI comparison.
        """

        if not query_text or not query_text.strip():
            return []

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        if not 0.0 <= contradiction_threshold <= 1.0:
            raise ValueError(
                "contradiction_threshold must be between 0 and 1."
            )

        results = self.chroma.search_by_text(
            query_text=query_text,
            top_k=top_k,
            embedder=self.embedder,
        )

        documents = results.get("documents", [[]])[0] or []
        metadatas = results.get("metadatas", [[]])[0] or []
        ids = results.get("ids", [[]])[0] or []
        distances = results.get("distances", [[]])[0] or []

        contradictions = []

        for article_id, document, metadata, distance in zip(
            ids,
            documents,
            metadatas,
            distances,
        ):
            metadata = metadata or {}

            # Skip empty documents.
            if not document or not document.strip():
                continue

            # Skip weak semantic matches before running the NLI model.
            if (
                distance is not None
                and distance > max_similarity_distance
            ):
                logger.debug(
                    "Skipping article %s because distance %.4f "
                    "exceeds %.4f.",
                    article_id,
                    distance,
                    max_similarity_distance,
                )
                continue

            prediction = self.nli.predict(
                query_text,
                document,
            )

            scores = prediction.get("scores", {})
            contradiction_score = scores.get(
                "contradiction",
                0.0,
            )

            if contradiction_score < contradiction_threshold:
                continue

            contradictions.append({
                "article_id": article_id,
                "title": metadata.get("title", ""),
                "source": metadata.get("source", "Unknown"),
                "topic": metadata.get("topic", "general"),
                "quality_score": metadata.get("quality_score", 0),
                "similarity_distance": round(
                    float(distance),
                    4,
                ) if distance is not None else None,
                "contradiction_score": contradiction_score,
                "entailment_score": scores.get(
                    "entailment",
                    0.0,
                ),
                "neutral_score": scores.get(
                    "neutral",
                    0.0,
                ),
                "matched_article": document,
            })

        contradictions.sort(
            key=lambda item: item["contradiction_score"],
            reverse=True,
        )

        logger.info(
            "Detected %d contradictions.",
            len(contradictions),
        )

        return contradictions