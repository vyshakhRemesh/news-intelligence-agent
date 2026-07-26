from datetime import datetime
from sqlalchemy import String, Text, DateTime, Float, Boolean, JSON ,Integer ,func, Column, ForeignKey, UniqueConstraint
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from src.config import Config
from datetime import datetime, timezone

from sqlalchemy.orm import relationship

class Base(DeclarativeBase):
    pass

class RawArticles(Base):
    __tablename__ = "raw_articles"
    
    # ============================================
    # BASIC FIELDS (Keep from main)
    # ============================================
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[str] = mapped_column(String(225), nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    # Add these fields to RawArticles class
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # fetched_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    
    # ============================================
    # NEW FIELDS (Add these)
    # ============================================
    
    # Preprocessing
    cleaned_title: Mapped[str] = mapped_column(Text, nullable=True)
    cleaned_content: Mapped[str] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(10), nullable=True)
    language_confidence: Mapped[float] = mapped_column(Float, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=True)      # ← Fixed!
    character_count: Mapped[int] = mapped_column(Integer, nullable=True) # ← Fixed!
    sentence_count: Mapped[int] = mapped_column(Integer, nullable=True)
    avg_word_length: Mapped[float] = mapped_column(Float, nullable=True)
    
    # Entity Extraction (spaCy)
    entities: Mapped[dict] = mapped_column(JSONB, default={}, nullable=True)
    
    # Enrichment
    sentiment: Mapped[dict] = mapped_column(JSONB, default={}, nullable=True)
    primary_topic: Mapped[str] = mapped_column(String(50), nullable=True)
    topics: Mapped[list] = mapped_column(JSONB, default=[], nullable=True)
    keyphrases: Mapped[list] = mapped_column(JSONB, default=[], nullable=True)
    readability: Mapped[dict] = mapped_column(JSONB, default={}, nullable=True)
    quality_score: Mapped[int] = mapped_column(Integer, default=0, nullable=True)
    language_complexity: Mapped[dict] = mapped_column(JSONB, default={}, nullable=True)
    enrichment_summary: Mapped[str] = mapped_column(Text, nullable=True)
    enriched_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    
    # Status
    preprocessing_status: Mapped[str] = mapped_column(String(50), default='pending', nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default='api', nullable=True)

    # Topic Modeling
    topic_id: Mapped[int] = mapped_column(Integer, nullable=True)
    primary_topic: Mapped[str] = mapped_column(String(50), nullable=True)
    topics: Mapped[list] = mapped_column(JSONB, default=[], nullable=True)
    
    def __repr__(self) -> str:
        return f"<RawArticle(id={self.id}, title={self.title[:30]}..., source={self.source_name})>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'title': self.title,
            'author': self.author,
            'source_name': self.source_name,
            'description': self.description[:200] + '...' if self.description and len(self.description) > 200 else self.description,
            'url': self.url,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'language': self.language,
            'primary_topic': self.primary_topic,
            'quality_score': self.quality_score,
            'sentiment': self.sentiment,
            'entities': self.entities,
            'enrichment_summary': self.enrichment_summary
        }

class ArticleRecommendation(Base):
    __tablename__ = "article_recommendations"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    article_id = Column(
        Integer,
        ForeignKey("raw_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Keep nullable for now because your test user
    # does not currently have a database user ID.
    user_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    trust_score = Column(
        Float,
        nullable=False,
    )

    confidence_score = Column(
        Float,
        nullable=False,
    )

    freshness_score = Column(
        Float,
        nullable=False,
    )

    interest_score = Column(
        Float,
        nullable=False,
    )

    source_preference_score = Column(
        Float,
        nullable=False,
    )

    recommendation_score = Column(
        Float,
        nullable=False,
        index=True,
    )

    calculated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    article = relationship(
        "RawArticles",
    )

class ArticleContradiction(Base):
    __tablename__ = "article_contradictions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    article_1_id = Column(
        Integer,
        ForeignKey("raw_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    article_2_id = Column(
        Integer,
        ForeignKey("raw_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    contradiction_score = Column(
        Float,
        nullable=False,
    )

    entailment_score = Column(
        Float,
        nullable=False,
    )

    neutral_score = Column(
        Float,
        nullable=False,
    )

    threshold_used = Column(
        Float,
        nullable=False,
    )

    detected_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "article_1_id",
            "article_2_id",
            name="uq_contradiction_article_pair",
        ),
    )

class DailyBriefing(Base):
    __tablename__ = 'daily_briefings'
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    topic_preferences: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # Stored as comma-separated string
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now()) # pylint: disable=not-callable
