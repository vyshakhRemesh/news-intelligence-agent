"""
Base client for all news API sources.
Provides session pooling, retry logic, and standardized date parsing.
"""
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class BaseNewsClient(ABC):
    """
    Abstract base class for news ingestion clients.

    Features:
    - requests.Session() for connection pooling
    - tenacity retry with exponential backoff
    - Robust ISO + RSS date parsing
    - Structured logging (no print statements)
    """

    def __init__(self, timeout: int = 10):
        self.session = requests.Session()
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=lambda e: isinstance(e, requests.RequestException),
        reraise=True,
    )
    def _get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> requests.Response:
        """Make a GET request with automatic retry on failure."""
        response = self.session.get(
            url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response

    def _parse_iso_date(self, date_value: Any) -> datetime:
        """
        Parse article dates from API and RSS sources.

        Handles:
        - ISO 8601 with Z or timezone offset (2024-01-15T10:30:00+00:00)
        - RSS formats (Mon, 01 Jan 2024 10:30:00 +0000)
        - None / missing values
        """
        if not date_value:
            return datetime.now()

        if isinstance(date_value, datetime):
            return date_value

        date_text = str(date_value).strip()

        # ISO 8601 with Z or timezone offset
        try:
            return datetime.fromisoformat(date_text.replace("Z", "+00:00"))
        except ValueError:
            pass

        # RSS formats
        rss_formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S %Z",
        ]

        for date_format in rss_formats:
            try:
                return datetime.strptime(date_text, date_format)
            except ValueError:
                continue

        logger.warning(
            "Could not parse date %r; using current time.",
            date_value,
        )
        return datetime.now()

    @abstractmethod
    def fetch_articles(self) -> List[Dict[str, Any]]:
        """
        Fetch articles from the source.

        Must return a list of dicts matching the ArticleDTO schema.
        """
        pass
