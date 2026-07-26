import logging
from typing import Dict, Any

import torch
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
)

from src.contradiction.contradiction_utils import normalize_text


logger = logging.getLogger(__name__)


class NLIModel:
    """
    Natural Language Inference model used to classify two texts as:

    - contradiction
    - entailment
    - neutral
    """

    DEFAULT_MODEL_NAME = "cross-encoder/nli-deberta-v3-small"

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        self.model_name = model_name

        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        logger.info(
            "Loading NLI model '%s' on %s",
            self.model_name,
            self.device,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name
        )

        self.model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name
        )

        self.model.to(self.device)
        self.model.eval()

        logger.info("NLI model loaded successfully.")

    def predict(self, text1: str, text2: str) -> Dict[str, Any]:
        """
        Compare two texts and return the predicted NLI relationship.

        Returns:
            {
                "label": "contradiction",
                "confidence": 0.91,
                "scores": {
                    "contradiction": 0.91,
                    "entailment": 0.03,
                    "neutral": 0.06
                }
            }
        """

        premise = normalize_text(text1)
        hypothesis = normalize_text(text2)

        if not premise or not hypothesis:
            return {
                "label": "neutral",
                "confidence": 0.0,
                "scores": {
                    "contradiction": 0.0,
                    "entailment": 0.0,
                    "neutral": 0.0,
                },
                "error": "Both texts are required for NLI comparison.",
            }

        encoded_input = self.tokenizer(
            premise,
            hypothesis,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        )

        encoded_input = {
            key: value.to(self.device)
            for key, value in encoded_input.items()
        }

        with torch.no_grad():
            output = self.model(**encoded_input)

        probabilities = torch.softmax(
            output.logits,
            dim=-1,
        )[0]

        scores = self._build_scores(probabilities)

        predicted_label = max(
            scores,
            key=scores.get,
        )

        return {
            "label": predicted_label,
            "confidence": round(scores[predicted_label], 4),
            "scores": {
                label: round(score, 4)
                for label, score in scores.items()
            },
        }

    def is_contradiction(
        self,
        text1: str,
        text2: str,
        threshold: float = 0.70,
    ) -> bool:
        """
        Return True when the contradiction confidence is at least
        the provided threshold.
        """

        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                "Contradiction threshold must be between 0 and 1."
            )

        result = self.predict(text1, text2)

        contradiction_score = result.get(
            "scores",
            {},
        ).get(
            "contradiction",
            0.0,
        )

        return contradiction_score >= threshold

    def _build_scores(
        self,
        probabilities: torch.Tensor,
    ) -> Dict[str, float]:
        """
        Map model output indexes to standard NLI labels.
        """

        scores = {
            "contradiction": 0.0,
            "entailment": 0.0,
            "neutral": 0.0,
        }

        id_to_label = self.model.config.id2label

        for index, probability in enumerate(probabilities):
            configured_label = id_to_label.get(
                index,
                str(index),
            )

            label = self._normalise_label(configured_label)

            if label in scores:
                scores[label] = probability.item()

        return scores

    @staticmethod
    def _normalise_label(label: str) -> str:
        """
        Convert model-specific labels into standard NLI labels.
        """

        normalised = str(label).strip().lower()

        if "contradiction" in normalised:
            return "contradiction"

        if "entailment" in normalised:
            return "entailment"

        if "neutral" in normalised:
            return "neutral"

        # Fallback for models exposing generic LABEL_n values.
        fallback_mapping = {
            "label_0": "contradiction",
            "label_1": "entailment",
            "label_2": "neutral",
        }

        return fallback_mapping.get(
            normalised,
            normalised,
        )