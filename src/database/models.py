from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from enum import Enum as PyEnum
from sqlalchemy import String, Text, DateTime, Float, Boolean, Integer, func, Column, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from src.config import Config


class Base(DeclarativeBase):
    pass


class UserRole(str, PyEnum):
    user = "user"
    admin = "admin"


class RawArticles(Base):
    __tablename__ = "raw_articles"

    # ============================================
    # BASIC FIELDS
    # ============================================
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(225), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Deduplication
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ============================================
    # PREPROCESSING FIELDS
    # ============================================
    cleaned_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cleaned_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    language_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    character_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sentence_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    avg_word_length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Entity Extraction (spaCy)
    entities: Mapped[Optional[dict]] = mapped_column(JSONB, default={}, nullable=True)

    # Enrichment
    sentiment: Mapped[Optional[dict]] = mapped_column(JSONB, default={}, nullable=True)
    primary_topic: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    topics: Mapped[Optional[list]] = mapped_column(JSONB, default=[], nullable=True)
    keyphrases: Mapped[Optional[list]] = mapped_column(JSONB, default=[], nullable=True)
    readability: Mapped[Optional[dict]] = mapped_column(JSONB, default={}, nullable=True)
    quality_score: Mapped[Optional[int]] = mapped_column(Integer, default=0, nullable=True)
    language_complexity: Mapped[Optional[dict]] = mapped_column(JSONB, default={}, nullable=True)
    enrichment_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enriched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Status
    preprocessing_status: Mapped[Optional[str]] = mapped_column(String(50), default="pending", nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(50), default="api", nullable=True)

    # Topic Modeling
    topic_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    primary_topic: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    topics: Mapped[Optional[list]] = mapped_column(JSONB, default=[], nullable=True)
    
    def __repr__(self) -> str:
        return f"<RawArticle(id={self.id}, title={self.title[:30]}..., source={self.source_name})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "source_name": self.source_name,
            "description": self.description[:200] + "..." if self.description and len(self.description) > 200 else self.description,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "language": self.language,
            "primary_topic": self.primary_topic,
            "quality_score": self.quality_score,
            "sentiment": self.sentiment,
            "entities": self.entities,
            "enrichment_summary": self.enrichment_summary
        }


class ArticleRecommendation(Base):
    __tablename__ = "article_recommendations"

    id = Column(Integer, primary_key=True, index=True)

    article_id = Column(
        Integer,
        ForeignKey(
            "raw_articles.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id = Column(
        Integer,
        nullable=True,
        index=True,
    )

    trust_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False)
    freshness_score = Column(Float, nullable=False)
    interest_score = Column(Float, nullable=False)
    source_preference_score = Column(Float, nullable=False)
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

    article = relationship("RawArticles")

    __table_args__ = (
        UniqueConstraint(
            "article_id",
            "user_id",
            name="uq_recommendation_article_user",
        ),
    )


class ArticleContradiction(Base):
    __tablename__ = "article_contradictions"

    id = Column(Integer, primary_key=True, index=True)
    article_1_id = Column(Integer, ForeignKey("raw_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    article_2_id = Column(Integer, ForeignKey("raw_articles.id", ondelete="CASCADE"), nullable=False, index=True)
    contradiction_score = Column(Float, nullable=False)
    entailment_score = Column(Float, nullable=False)
    neutral_score = Column(Float, nullable=False)
    threshold_used = Column(Float, nullable=False)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        UniqueConstraint("article_1_id", "article_2_id", name="uq_contradiction_article_pair"),
    )


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    topic_preferences: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# USER TABLES  (now with role + relationships)
# ============================================================

class User(Base):
    __tablename__ = "users"
    id         = Column(String(100), primary_key=True, index=True)
    username   = Column(String(100), unique=True, nullable=False)
    email      = Column(String(255), unique=True, nullable=False)
    full_name  = Column(String(255), nullable=True)
    name       = Column(String(255), nullable=True)          # backward-compat for platform_agent
    role       = Column(SQLEnum(UserRole), default=UserRole.user, nullable=False)
    is_active  = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    query_logs  = relationship("UserQueryLog", back_populates="user", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"
    id      = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(100), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic   = Column(String(100), nullable=False)
    weight  = Column(Float, default=1.0)

    user = relationship("User", back_populates="preferences")


class UserQueryLog(Base):
    __tablename__ = "user_query_logs"
    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(String(100), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query      = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="query_logs")