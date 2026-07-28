"""
Shared Article Data Transfer Object for type-safe ingestion.
All clients return ArticleDTO which is converted to dict for backward compatibility.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class ArticleDTO:
    """Standardized article schema across all ingestion sources."""
    title: str
    source_name: str
    source_type: str
    url: str
    description: str = ""
    content: str = ""
    author: str = ""
    published_at: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dict for backward compatibility with main.py."""
        return asdict(self)
