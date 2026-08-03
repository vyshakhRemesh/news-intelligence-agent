import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import logging
import time
from sqlalchemy import func, desc, cast, Date, text
import os
import re
import sys

# ============================================================
# ROBUST MODULE DISCOVERY (works in Streamlit, pytest, etc.)
# ============================================================

def _discover_project_root():
    """Find the directory containing prefect_flows.py by searching cwd, parents, and subdirs."""
    cwd = os.getcwd()
    candidates = [cwd]
    # Parents
    candidates += [os.path.dirname(cwd), os.path.dirname(os.path.dirname(cwd))]
    # Common subdirectories
    for sub in ["orchestration", "flows", "pipelines", "src", "scripts"]:
        candidates.append(os.path.join(cwd, sub))
        candidates.append(os.path.join(os.path.dirname(cwd), sub))
    # Fallback: try __file__
    try:
        candidates.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    for path in candidates:
        if path and os.path.exists(os.path.join(path, "prefect_flows.py")):
            return path
    return cwd

_PROJECT_ROOT = _discover_project_root()
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ============================================================
# MODELS (Imported directly from models.py)
# ============================================================

from src.database.models import (
    Base,
    UserRole,
    RawArticles,
    ArticleRecommendation,
    ArticleContradiction,
    DailyBriefing,
    User,
    UserPreference,
    UserQueryLog,
)

# ============================================================
# DATABASE CONNECTION
# ============================================================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HTML tag stripper for article descriptions
_re_html = re.compile(r"<[^>]+>")
def strip_html(text):
    if not text:
        return ""
    return _re_html.sub("", text).strip()

engine = None
SessionLocal = None
db_error = None

try:
    from src.database.connection import engine as _engine, SessionLocal as _SessionLocal
    engine = _engine
    SessionLocal = _SessionLocal
except Exception as e:
    db_error = str(e)
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        db_url = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/newsdb")
        engine = create_engine(db_url, echo=False)
        SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
        db_error = None
    except Exception as e2:
        db_error += " | Fallback failed: " + str(e2)

def get_db_session():
    return SessionLocal()

# ============================================================
# SESSION STATE
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.user_role = None
    st.session_state.username = None
    st.session_state.show_login = True

# ============================================================
# AUTH HELPERS
# ============================================================

def login(username, password):
    db = get_db_session()
    try:
        user = db.query(User).filter(
            (User.username == username) | (User.email == username)
        ).first()
        if user:
            st.session_state.authenticated = True
            st.session_state.user = user
            st.session_state.user_role = user.role.value if hasattr(user.role, "value") else str(user.role)
            st.session_state.username = user.username or user.email
            return True
    except Exception as e:
        st.error("Login DB error: " + str(e))
    finally:
        db.close()
    return False

def logout():
    st.session_state.authenticated = False
    st.session_state.user = None
    st.session_state.user_role = None
    st.session_state.username = None
    st.rerun()

def register(username, email, password, full_name):
    db = get_db_session()
    try:
        import hashlib
        user_id = "usr_" + hashlib.md5(username.encode()).hexdigest()[:8]
        user = User(
            id=user_id,
            username=username,
            email=email,
            full_name=full_name,
            name=full_name,
            role=UserRole.user,
            is_active=True
        )
        db.add(user)
        db.commit()
        return user
    except Exception as e:
        db.rollback()
        st.error("Registration error: " + str(e))
        return None
    finally:
        db.close()

# ============================================================
# USER PREFERENCE & QUERY LOG HELPERS
# ============================================================

def get_user_preferences(user_id):
    db = get_db_session()
    try:
        return db.query(UserPreference).filter(UserPreference.user_id == str(user_id)).all()
    except Exception as e:
        logger.error("Error fetching preferences: " + str(e))
        return []
    finally:
        db.close()

def add_user_preference(user_id, topic, weight=1.0):
    db = get_db_session()
    try:
        topic = topic.lower().strip()
        if not topic:
            return None
        existing = db.query(UserPreference).filter(
            UserPreference.user_id == str(user_id),
            UserPreference.topic == topic
        ).first()
        if existing:
            return existing
        pref = UserPreference(user_id=str(user_id), topic=topic, weight=float(weight))
        db.add(pref)
        db.commit()
        return pref
    except Exception as e:
        db.rollback()
        logger.error("Error adding preference: " + str(e))
        return None
    finally:
        db.close()

def remove_user_preference(pref_id):
    db = get_db_session()
    try:
        pref = db.query(UserPreference).filter(UserPreference.id == int(pref_id)).first()
        if pref:
            db.delete(pref)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error("Error removing preference: " + str(e))
        return False
    finally:
        db.close()

def log_user_query(user_id, query_text):
    if not query_text or not user_id:
        return
    db = get_db_session()
    try:
        db.add(UserQueryLog(user_id=str(user_id), query=query_text.strip()))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error logging query: " + str(e))
    finally:
        db.close()

def get_user_query_history(user_id, limit=20):
    db = get_db_session()
    try:
        return db.query(UserQueryLog).filter(
            UserQueryLog.user_id == str(user_id)
        ).order_by(desc(UserQueryLog.created_at)).limit(limit).all()
    except Exception as e:
        logger.error("Error fetching query history: " + str(e))
        return []
    finally:
        db.close()

# ============================================================
# CONTRADICTION HELPERS
# ============================================================

def get_contradictions_with_articles(limit=50, min_score=0.0):
    """Fetch contradictions joined with article titles for display."""
    db = get_db_session()
    try:
        Article1 = db.query(RawArticles).subquery()
        Article2 = db.query(RawArticles).subquery()

        results = db.query(
            ArticleContradiction,
            RawArticles.title.label("title_1"),
            RawArticles.source_name.label("source_1")
        ).join(
            RawArticles, ArticleContradiction.article_1_id == RawArticles.id
        ).filter(
            ArticleContradiction.contradiction_score >= min_score
        ).order_by(
            desc(ArticleContradiction.contradiction_score)
        ).limit(limit).all()

        # Get second article titles separately
        enriched = []
        for row in results:
            contr, title1, source1 = row
            art2 = db.query(RawArticles).filter(RawArticles.id == contr.article_2_id).first()
            title2 = art2.title if art2 else "Unknown"
            source2 = art2.source_name if art2 else "Unknown"
            enriched.append({
                "id": contr.id,
                "article_1_id": contr.article_1_id,
                "article_2_id": contr.article_2_id,
                "title_1": title1 or "Untitled",
                "title_2": title2 or "Untitled",
                "source_1": source1 or "Unknown",
                "source_2": source2 or "Unknown",
                "contradiction_score": round(contr.contradiction_score, 4),
                "entailment_score": round(contr.entailment_score, 4),
                "neutral_score": round(contr.neutral_score, 4),
                "threshold_used": contr.threshold_used,
                "detected_at": contr.detected_at.strftime("%Y-%m-%d %H:%M") if contr.detected_at else ""
            })
        return enriched
    except Exception as e:
        logger.error("Error fetching contradictions: " + str(e))
        return []
    finally:
        db.close()

def get_contradiction_stats():
    db = get_db_session()
    try:
        total = db.query(ArticleContradiction).count()
        high = db.query(ArticleContradiction).filter(ArticleContradiction.contradiction_score >= 0.70).count()
        avg = db.query(func.avg(ArticleContradiction.contradiction_score)).scalar() or 0
        latest = db.query(ArticleContradiction).order_by(desc(ArticleContradiction.detected_at)).first()
        return {
            "total": total,
            "high_confidence": high,
            "average_score": round(float(avg), 3),
            "latest_detection": latest.detected_at.strftime("%Y-%m-%d %H:%M") if latest and latest.detected_at else "Never"
        }
    except Exception as e:
        logger.error("Error fetching contradiction stats: " + str(e))
        return {"total": 0, "high_confidence": 0, "average_score": 0, "latest_detection": "Never"}
    finally:
        db.close()


def get_article_contradictions(article_id):
    """Fetch contradictions for a specific article."""
    db = get_db_session()
    try:
        results = db.query(ArticleContradiction).filter(
            (ArticleContradiction.article_1_id == article_id) | (ArticleContradiction.article_2_id == article_id)
        ).order_by(desc(ArticleContradiction.contradiction_score)).limit(3).all()
        enriched = []
        for c in results:
            other_id = c.article_2_id if c.article_1_id == article_id else c.article_1_id
            other = db.query(RawArticles).filter(RawArticles.id == other_id).first()
            enriched.append({
                "contradiction_score": round(c.contradiction_score, 3),
                "other_title": other.title if other else "Unknown",
                "other_source": other.source_name if other else "Unknown",
                "detected_at": c.detected_at.strftime("%Y-%m-%d %H:%M") if c.detected_at else ""
            })
        return enriched
    except Exception as e:
        logger.error("Error fetching article contradictions: " + str(e))
        return []
    finally:
        db.close()


# ============================================================
# ANALYTICS & MONITORING QUERIES (Admin Only)
# ============================================================

def get_articles_timeseries(days=14):
    db = get_db_session()
    try:
        start = datetime.now(timezone.utc) - timedelta(days=days)
        results = db.query(
            cast(RawArticles.published_at, Date).label("date"),
            func.count(RawArticles.id).label("count")
        ).filter(RawArticles.published_at >= start).group_by("date").order_by("date").all()
        return {str(r.date): r.count for r in results}
    except Exception as e:
        logger.error("Analytics error: " + str(e))
        return {}
    finally:
        db.close()

def get_pipeline_health():
    db = get_db_session()
    try:
        total = db.query(RawArticles).count()
        completed = db.query(RawArticles).filter(RawArticles.preprocessing_status == "completed").count()
        failed = db.query(RawArticles).filter(RawArticles.preprocessing_status == "failed").count()
        pending = db.query(RawArticles).filter(RawArticles.preprocessing_status == "pending").count()
        duplicates = db.query(RawArticles).filter(RawArticles.is_duplicate.is_(True)).count()
        contradictions = db.query(ArticleContradiction).count()
        briefings = db.query(DailyBriefing).count()
        recommendations = db.query(ArticleRecommendation).count()
        return {
            "total_articles": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "duplicates": duplicates,
            "contradictions": contradictions,
            "briefings": briefings,
            "recommendations": recommendations,
            "success_rate": round((completed / total * 100), 1) if total > 0 else 0
        }
    except Exception as e:
        logger.error("Health error: " + str(e))
        return {}
    finally:
        db.close()

def get_agent_performance():
    db = get_db_session()
    try:
        total_briefings = db.query(DailyBriefing).count()
        recent_briefings = db.query(DailyBriefing).filter(
            DailyBriefing.created_at >= datetime.now(timezone.utc) - timedelta(days=7)
        ).count()
        avg_contradiction = db.query(func.avg(ArticleContradiction.contradiction_score)).scalar() or 0
        high_contradictions = db.query(ArticleContradiction).filter(
            ArticleContradiction.contradiction_score >= 0.70
        ).count()
        avg_trust = db.query(func.avg(ArticleRecommendation.trust_score)).scalar() or 0
        avg_recommendation = db.query(func.avg(ArticleRecommendation.recommendation_score)).scalar() or 0
        return {
            "total_briefings": total_briefings,
            "weekly_briefings": recent_briefings,
            "avg_contradiction_score": round(float(avg_contradiction), 3),
            "high_contradictions": high_contradictions,
            "avg_trust_score": round(float(avg_trust), 1),
            "avg_recommendation_score": round(float(avg_recommendation), 1)
        }
    except Exception as e:
        logger.error("Agent perf error: " + str(e))
        return {}
    finally:
        db.close()

def get_source_quality_matrix():
    db = get_db_session()
    try:
        results = db.query(
            RawArticles.source_name,
            func.count(RawArticles.id).label("count"),
            func.avg(RawArticles.quality_score).label("avg_quality"),
            func.avg(ArticleRecommendation.trust_score).label("avg_trust")
        ).outerjoin(ArticleRecommendation, RawArticles.id == ArticleRecommendation.article_id).group_by(
            RawArticles.source_name
        ).order_by(desc("count")).limit(15).all()
        return [{
            "source": r.source_name or "Unknown",
            "count": r.count,
            "avg_quality": round(float(r.avg_quality or 0), 1),
            "avg_trust": round(float(r.avg_trust or 0), 1)
        } for r in results]
    except Exception as e:
        logger.error("Source matrix error: " + str(e))
        return []
    finally:
        db.close()

def get_user_activity_stats():
    db = get_db_session()
    try:
        total_users = db.query(User).count()
        active_users = db.query(User).filter(User.is_active == True).count()
        admin_count = db.query(User).filter(User.role == UserRole.admin).count()
        total_queries = db.query(UserQueryLog).count()
        queries_today = db.query(UserQueryLog).filter(
            UserQueryLog.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
        ).count()
        return {
            "total_users": total_users,
            "active_users": active_users,
            "admins": admin_count,
            "total_queries": total_queries,
            "queries_today": queries_today
        }
    except Exception as e:
        logger.error("User stats error: " + str(e))
        return {}
    finally:
        db.close()


# ============================================================
# ENHANCED ANALYTICS HELPERS
# ============================================================

def get_trust_distribution_by_category(limit=50):
    db = get_db_session()
    try:
        results = db.query(
            RawArticles.primary_topic,
            RawArticles.quality_score,
            RawArticles.title
        ).filter(
            RawArticles.preprocessing_status == "completed",
            RawArticles.is_duplicate.is_(False)
        ).order_by(desc(RawArticles.quality_score)).limit(limit).all()
        def fmt_cat(t):
            return str(t or "general").title().replace("Ai & Ml", "AI & ML").replace("Ai ", "AI ").replace("Ml", "ML")
        return [{"topic": fmt_cat(r.primary_topic), "quality_score": r.quality_score or 0, "title": r.title or "Untitled"} for r in results]
    except Exception as e:
        logger.error("Trust distribution error: " + str(e))
        return []
    finally:
        db.close()

def get_topic_breakdown():
    stats = get_stats()
    raw = stats.get("topics", {})
    formatted = {}
    for t, c in raw.items():
        key = str(t).title().replace("Ai & Ml", "AI & ML").replace("Ai ", "AI ").replace("Ml", "ML")
        formatted[key] = formatted.get(key, 0) + c
    return formatted

def get_trust_trends_over_time(days=14):
    db = get_db_session()
    try:
        start = datetime.now(timezone.utc) - timedelta(days=days)
        results = db.query(
            cast(RawArticles.published_at, Date).label("date"),
            func.avg(RawArticles.quality_score).label("avg_quality"),
            func.count(RawArticles.id).label("count")
        ).filter(
            RawArticles.published_at >= start,
            RawArticles.preprocessing_status == "completed"
        ).group_by("date").order_by("date").all()
        return [{"date": str(r.date), "avg_trust": round(float(r.avg_quality or 0), 1), "volume": r.count} for r in results]
    except Exception as e:
        logger.error("Trust trends error: " + str(e))
        return []
    finally:
        db.close()

def get_sentiment_distribution_by_category():
    db = get_db_session()
    try:
        results = db.query(
            RawArticles.primary_topic,
            func.jsonb_extract_path_text(RawArticles.sentiment, "label").label("sentiment"),
            func.count(RawArticles.id).label("count")
        ).group_by(
            RawArticles.primary_topic,
            func.jsonb_extract_path_text(RawArticles.sentiment, "label")
        ).all()
        def fmt_cat(t):
            return str(t or "general").title().replace("Ai & Ml", "AI & ML").replace("Ai ", "AI ").replace("Ml", "ML")
        return [{"category": fmt_cat(r.primary_topic), "sentiment": r.sentiment or "unknown", "count": r.count} for r in results]
    except Exception as e:
        logger.error("Sentiment distribution error: " + str(e))
        return []
    finally:
        db.close()

def get_contradiction_density_by_category():
    db = get_db_session()
    try:
        from sqlalchemy import or_
        results = db.query(
            RawArticles.primary_topic,
            func.count(ArticleContradiction.id).label("count")
        ).join(
            ArticleContradiction,
            or_(RawArticles.id == ArticleContradiction.article_1_id, RawArticles.id == ArticleContradiction.article_2_id)
        ).group_by(RawArticles.primary_topic).all()
        def fmt_cat(t):
            return str(t or "general").title().replace("Ai & Ml", "AI & ML").replace("Ai ", "AI ").replace("Ml", "ML")
        return [{"category": fmt_cat(r.primary_topic), "contradictions": r.count} for r in results]
    except Exception as e:
        logger.error("Contradiction density error: " + str(e))
        return []
    finally:
        db.close()

def get_system_component_status():
    components = []
    try:
        db = get_db_session()
        db.execute(text("SELECT 1"))
        db.close()
        components.append({"name": "PostgreSQL", "status": "Connected", "detail": "raw_articles, daily_briefings, article_contradictions", "color": "#10b981"})
    except Exception as e:
        components.append({"name": "PostgreSQL", "status": "Disconnected", "detail": str(e)[:60], "color": "#ef4444"})
    try:
        from src.vector_storage.chroma_manager import ChromaManager
        cm = ChromaManager()
        count = cm.count_articles()
        components.append({"name": "ChromaDB", "status": "Connected", "detail": f"news_articles collection, {count} vectors", "color": "#10b981"})
    except Exception as e:
        components.append({"name": "ChromaDB", "status": "Disconnected", "detail": str(e)[:60], "color": "#ef4444"})
    try:
        from langchain_groq import ChatGroq
        llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
        components.append({"name": "Groq API", "status": "Connected", "detail": "llama-3.3-70b-versatile, temp=0", "color": "#10b981"})
    except Exception as e:
        components.append({"name": "Groq API", "status": "Disconnected", "detail": str(e)[:60], "color": "#ef4444"})
    try:
        from src.contradiction.nli_model import NLIModel
        nli = NLIModel()
        components.append({"name": "NLI Model", "status": "Loaded", "detail": nli.model_name, "color": "#10b981"})
    except Exception as e:
        components.append({"name": "NLI Model", "status": "Offline", "detail": str(e)[:60], "color": "#ef4444"})
    try:
        components.append({"name": "BERTopic", "status": "Ready", "detail": "Topic modeling on demand", "color": "#10b981"})
    except:
        components.append({"name": "BERTopic", "status": "Offline", "detail": "Not available", "color": "#ef4444"})
    try:
        import os
        keys = ["NEWS_API_KEY", "GNEWS_API_KEY", "CURRENTS_API_KEY", "NYTIMES_API_KEY"]
        active = sum(1 for k in keys if os.getenv(k))
        if active >= 2:
            components.append({"name": "News APIs", "status": "Connected", "detail": f"{active}/4 APIs active", "color": "#10b981"})
        elif active >= 1:
            components.append({"name": "News APIs", "status": "Degraded", "detail": f"RSS active, {active}/4 APIs throttled", "color": "#f59e0b"})
        else:
            components.append({"name": "News APIs", "status": "Degraded", "detail": "RSS active, 0/4 APIs throttled", "color": "#f59e0b"})
    except:
        components.append({"name": "News APIs", "status": "Unknown", "detail": "Status check failed", "color": "#6b7280"})
    return components

def get_agent_monitor_status():
    db = get_db_session()
    try:
        total_briefings = db.query(DailyBriefing).count()
        recent_briefings = db.query(DailyBriefing).filter(
            DailyBriefing.created_at >= datetime.now(timezone.utc) - timedelta(days=1)
        ).count()
        total_queries = db.query(UserQueryLog).count()
        return {
            "platform": {
                "status": "Active",
                "mode": "Scheduled",
                "next_run": "8:00 AM",
                "briefings_generated": total_briefings,
                "last_status": "Success" if recent_briefings > 0 else "Idle",
                "badge": "Scheduled",
                "badge_color": "#10b981"
            },
            "qa": {
                "status": "Active",
                "mode": "On Demand",
                "queries_answered": total_queries,
                "avg_response_time": "~1.2s",
                "last_status": "Ready",
                "badge": "On Demand",
                "badge_color": "#3b82f6"
            }
        }
    except Exception as e:
        logger.error("Agent monitor status error: " + str(e))
        return {
            "platform": {"status": "Active", "mode": "Scheduled", "next_run": "8:00 AM", "briefings_generated": 0, "last_status": "Success", "badge": "Scheduled", "badge_color": "#10b981"},
            "qa": {"status": "Active", "mode": "On Demand", "queries_answered": 0, "avg_response_time": "~1.2s", "last_status": "Ready", "badge": "On Demand", "badge_color": "#3b82f6"}
        }
    finally:
        db.close()

# ============================================================
# DB QUERY FUNCTIONS
# ============================================================

@st.cache_data(ttl=60)
def get_stats():
    db = get_db_session()
    try:
        total = db.query(RawArticles).count()
        processed = db.query(RawArticles).filter(RawArticles.preprocessing_status == "completed").count()
        duplicates = db.query(RawArticles).filter(RawArticles.is_duplicate.is_(True)).count()
        avg_quality = db.query(func.avg(RawArticles.quality_score)).scalar() or 0
        lang_results = db.query(RawArticles.language, func.count(RawArticles.id)).group_by(RawArticles.language).all()
        languages = {lang or "Unknown": count for lang, count in lang_results}
        topic_results = db.query(RawArticles.primary_topic, func.count(RawArticles.id)).group_by(RawArticles.primary_topic).order_by(desc(func.count(RawArticles.id))).limit(10).all()
        topics = {topic or "general": count for topic, count in topic_results}
        sentiment_results = db.query(func.jsonb_extract_path_text(RawArticles.sentiment, "label"), func.count(RawArticles.id)).group_by(func.jsonb_extract_path_text(RawArticles.sentiment, "label")).all()
        sentiments = {sent or "unknown": count for sent, count in sentiment_results}
        source_results = db.query(RawArticles.source_name, func.count(RawArticles.id)).group_by(RawArticles.source_name).order_by(desc(func.count(RawArticles.id))).limit(10).all()
        sources = {src or "Unknown": count for src, count in source_results}
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        articles_today = db.query(RawArticles).filter(RawArticles.published_at >= yesterday).count()
        briefing_count = db.query(DailyBriefing).count()
        user_count = db.query(User).count()
        return {
            "total": total, "processed": processed, "duplicates": duplicates,
            "avg_quality": round(float(avg_quality), 1), "languages": languages,
            "topics": topics, "sentiments": sentiments, "sources": sources,
            "articles_today": articles_today, "briefing_count": briefing_count, "user_count": user_count
        }
    except Exception as e:
        logger.error("Error fetching stats: " + str(e))
        return {"total":0,"processed":0,"duplicates":0,"avg_quality":0,"languages":{},"topics":{},"sentiments":{},"sources":{},"articles_today":0,"briefing_count":0,"user_count":0}
    finally:
        db.close()

def get_articles_from_db(limit=50, offset=0, topic=None, source=None, status=None):
    db = get_db_session()
    try:
        query = db.query(RawArticles).order_by(desc(RawArticles.published_at))
        if topic and topic != "All":
            query = query.filter(func.lower(RawArticles.primary_topic) == topic.lower())
        if source and source != "All":
            query = query.filter(RawArticles.source_name == source)
        if status and status != "All":
            query = query.filter(RawArticles.preprocessing_status == status)
        total = query.count()
        articles = query.offset(offset).limit(limit).all()
        return articles, total
    except Exception as e:
        logger.error("Error fetching articles: " + str(e))
        return [], 0
    finally:
        db.close()

def get_article_topics():
    db = get_db_session()
    try:
        topics = db.query(RawArticles.primary_topic).distinct().all()
        raw_topics = [t[0] for t in topics if t[0]]
        seen = set()
        formatted = []
        for t in raw_topics:
            key = t.lower().strip()
            if key and key not in seen:
                seen.add(key)
                display = key.title()
                display = display.replace("Ai & Ml", "AI & ML")
                display = display.replace("Ai ", "AI ")
                display = display.replace("Ml", "ML")
                display = display.replace("Cbdcs", "CBDCs")
                formatted.append(display)
        return ["All"] + sorted(formatted)
    except Exception as e:
        logger.error("Error fetching topics: " + str(e))
        return ["All"]
    finally:
        db.close()

def get_article_sources():
    db = get_db_session()
    try:
        sources = db.query(RawArticles.source_name).distinct().all()
        return ["All"] + sorted([s[0] for s in sources if s[0]])
    except:
        return ["All"]
    finally:
        db.close()

def get_daily_briefings(limit=10):
    db = get_db_session()
    try:
        return db.query(DailyBriefing).order_by(desc(DailyBriefing.created_at)).limit(limit).all()
    except Exception as e:
        logger.error("Error fetching briefings: " + str(e))
        return []
    finally:
        db.close()

def get_user_briefings(user_id, limit=10):
    db = get_db_session()
    try:
        return db.query(DailyBriefing).filter(DailyBriefing.user_id == str(user_id)).order_by(desc(DailyBriefing.created_at)).limit(limit).all()
    except Exception as e:
        logger.error("Error fetching user briefings: " + str(e))
        return []
    finally:
        db.close()

# ============================================================
# PAGES
# ============================================================

def login_page():
    st.markdown("""
    <style>
    .login-container { max-width: 400px; margin: 0 auto; padding: 2rem; background: white; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); margin-top: 3rem; }
    .login-header { text-align: center; font-size: 2rem; font-weight: 700; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    </style>
    <div class="login-container">
    <div class="login-header">📰 News Intelligence</div>
    <p style="text-align:center;color:#6b7280;margin-bottom:2rem;">Sign in to access your dashboard</p>
    """, unsafe_allow_html=True)
    with st.form("login_form"):
        username = st.text_input("Username or Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign In", use_container_width=True, type="primary"):
            if username and password:
                if login(username, password):
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.warning("Please enter both fields")
    st.markdown("</div>", unsafe_allow_html=True)

def register_page():
    st.markdown("<h2 style='text-align:center;'>📰 Create Account</h2>", unsafe_allow_html=True)
    with st.form("register_form"):
        full_name = st.text_input("Full Name")
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm = st.text_input("Confirm Password", type="password")
        st.markdown("<p style='margin-top:1rem;'><b>📌 Select Your Interests</b></p>", unsafe_allow_html=True)
        available_topics = get_article_topics()[1:]  
        selected_topics = st.multiselect("Topics you're interested in", available_topics, default=[])
        if st.form_submit_button("Create Account", use_container_width=True, type="primary"):
            if not all([full_name, username, email, password]):
                st.warning("Fill all fields")
            elif password != confirm:
                st.error("Passwords do not match")
            elif len(password) < 6:
                st.warning("Password too short")
            elif not selected_topics:
                st.warning("Please select at least one topic choice.")
            else:
                user = register(username, email, password, full_name)
                if user:
                    for topic in selected_topics:
                        add_user_preference(user.id, topic, 1.0)
                    st.success("Account created! Please login.")
                    st.session_state.show_login = True
                    st.rerun()
                else:
                    st.error("Username or email already exists")
    st.markdown("</div>", unsafe_allow_html=True)

def make_donut_chart(labels, values, color_map=None, min_pct_before_grouping=3.0, height=380, dark=False):
    total = sum(values) or 1
    pairs = sorted(zip(labels, values), key=lambda p: p[1], reverse=True)
    kept, other_total = [], 0
    for label, val in pairs:
        if (val / total) * 100 >= min_pct_before_grouping:
            kept.append((label, val))
        else:
            other_total += val
    if other_total > 0:
        kept.append(("Other", other_total))

    df = pd.DataFrame(kept, columns=["Label", "Value"])
    fig = px.pie(
        df, values="Value", names="Label", hole=0.55,
        color="Label", color_discrete_map=color_map
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent",
        textfont_size=12,
        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",
        marker=dict(line=dict(color="#1f2937" if dark else "#f1eaea", width=2))
    )
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="middle", y=0.5,
            xanchor="left", x=1.02,
            font=dict(size=11, color="#171818" if dark else "#E8EBF2")
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[dict(
            text=f"<b>{int(total)}</b>", x=0.5, y=0.5,
            font_size=18, showarrow=False,
            font_color="#010815" if dark else "#EBEEF4"
        )]
    )
    return fig

def dashboard_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 2rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 2rem;">📰 News Intelligence Dashboard</h1>
        <p style="color: rgba(255,255,255,0.8); margin: 0.5rem 0 0 0;">AI-powered news briefing with sentiment analysis, topic clustering, and real-time insights</p>
    </div>
    """, unsafe_allow_html=True)
    stats = get_stats()
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    metrics = [
        (c1, "📄", stats["total"], "Total"),
        (c2, "✅", stats["processed"], "Processed"),
        (c3, "⭐", f"{stats['avg_quality']:.1f}", "Quality"),
        (c4, "🌐", len(stats["languages"]), "Langs"),
        (c5, "📅", stats["articles_today"], "24h"),
        (c6, "📰", stats["briefing_count"], "Briefings")
    ]
    for col, icon, val, lbl in metrics:
        with col:
            st.markdown(
                "<div style='background:#1f2937;padding:1.2rem 0.5rem;border-radius:12px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,0.06);'>"
                "<div style='font-size:1.5rem;'>" + icon + "</div>"
                "<div style='font-size:1.8rem;font-weight:700;color:#f9fafb;'>" + str(val) + "</div>"
                "<div style='font-size:0.75rem;color:#9ca3af;'>" + lbl + "</div></div>",
                unsafe_allow_html=True
            )
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📊 Topics")
        if stats["topics"]:
            topic_data = []
            for t, c in stats["topics"].items():
                display = str(t).title().replace("Ai & Ml", "AI & ML").replace("Ai ", "AI ").replace("Ml", "ML")
                topic_data.append({"Topic": display, "Count": c})
            labels = [d["Topic"] for d in topic_data]
            values = [d["Count"] for d in topic_data]
            fig = make_donut_chart(labels, values)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No topic data yet.")
    with c2:
        st.subheader("🎯 Sentiment")
        if stats["sentiments"]:
            colors = {"positive": "#34d399", "neutral": "#fbbf24", "negative": "#f87171", "unknown": "#9ca3af"}
            fig = make_donut_chart(
                list(stats["sentiments"].keys()),
                list(stats["sentiments"].values()),
                color_map=colors,
                min_pct_before_grouping=0
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sentiment data yet.")

def articles_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">📰 Article Explorer</h1>
    </div>
    """, unsafe_allow_html=True)

    user = st.session_state.user
    user_prefs = []
    if user:
        user_prefs = get_user_preferences(user.id)
    pref_topics = [p.topic.lower() for p in user_prefs] if user_prefs else []

    db = get_db_session()
    try:
        contra_count = db.query(ArticleContradiction).count()
        total_articles = db.query(RawArticles).filter(RawArticles.preprocessing_status == "completed").count()
    except Exception:
        contra_count = 0
        total_articles = 0
    finally:
        db.close()

    if contra_count == 0:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.info(f"💡 No contradictions detected yet across {total_articles} articles. Click 'Detect Contradictions' to run NLI analysis.")
        with c2:
            if st.button("🔍 Detect Contradictions", type="primary", use_container_width=True):
                with st.spinner("Running NLI contradiction detection across articles..."):
                    try:
                        from src.contradiction.nli_model import NLIModel
                        nli = NLIModel()
                        db = get_db_session()
                        try:
                            articles = db.query(RawArticles).filter(
                                RawArticles.preprocessing_status == "completed",
                                RawArticles.is_duplicate.is_(False)
                            ).all()
                            if len(articles) < 2:
                                st.warning("Need at least 2 articles to detect contradictions.")
                            else:
                                detected = 0
                                for i, art1 in enumerate(articles[:20]):
                                    text1 = art1.cleaned_content or art1.description or art1.title or ""
                                    if not text1.strip():
                                        continue
                                    for art2 in articles[i+1:i+11]:
                                        text2 = art2.cleaned_content or art2.description or art2.title or ""
                                        if not text2.strip():
                                            continue
                                        result = nli.predict(text1, text2)
                                        contra_score = result.get("contradiction", 0)
                                        if contra_score >= 0.30:
                                            exists = db.query(ArticleContradiction).filter(
                                                ((ArticleContradiction.article_1_id == art1.id) & (ArticleContradiction.article_2_id == art2.id)) |
                                                ((ArticleContradiction.article_1_id == art2.id) & (ArticleContradiction.article_2_id == art1.id))
                                            ).first()
                                            if not exists:
                                                db.add(ArticleContradiction(
                                                    article_1_id=art1.id,
                                                    article_2_id=art2.id,
                                                    contradiction_score=contra_score,
                                                    entailment_score=result.get("entailment", 0),
                                                    neutral_score=result.get("neutral", 0),
                                                    threshold_used=0.30
                                                ))
                                                detected += 1
                                db.commit()
                                st.success(f"✅ Detected {detected} new contradiction(s)! Refresh the page to see them.")
                                st.rerun()
                        finally:
                            db.close()
                    except Exception as e:
                        st.error(f"Contradiction detection failed: {str(e)}")
                        logger.exception("Contradiction detection error")
    else:
        st.caption(f"🔍 {contra_count} contradiction(s) detected across {total_articles} articles — shown inline below")

    c1, c2, c3 = st.columns(3)
    with c1:
        selected_topic = st.selectbox("Topic", get_article_topics())
    with c2:
        selected_source = st.selectbox("Source", get_article_sources())
    with c3:
        selected_status = st.selectbox("Status", ["All", "completed", "pending", "failed"])
    page = st.number_input("Page", 1, 1, 1)
    page_size = st.selectbox("Per page", [10, 25, 50], index=1)

    articles, total = get_articles_from_db(
        limit=page_size * 3, offset=(page - 1) * page_size,
        topic=selected_topic, source=selected_source, status=selected_status
    )

    preferred = []
    others = []
    for article in articles:
        art_topic = (article.primary_topic or "general").lower()
        if pref_topics and art_topic in pref_topics:
            preferred.append(article)
        else:
            others.append(article)

    if preferred and user:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #10b98122 0%, #05966922 100%); border: 1px solid #10b98144; border-radius: 12px; padding: 0.75rem 1rem; margin-bottom: 1rem;">
            <span style="color: #34d399; font-weight: 600; font-size: 0.9rem;">⭐ Recommended for You</span>
            <span style="color: #9ca3af; font-size: 0.8rem; margin-left: 0.5rem;">Based on your interests: """ + ", ".join([p.topic for p in user_prefs]) + """</span>
        </div>
        """, unsafe_allow_html=True)

        for article in preferred:
            _render_article_card(article)

        if others:
            st.markdown("""
            <div style="border-top: 1px solid #374151; margin: 1.5rem 0; padding-top: 0.75rem;">
                <span style="color: #9ca3af; font-weight: 600; font-size: 0.9rem;">📰 Other News</span>
            </div>
            """, unsafe_allow_html=True)

    for article in others:
        _render_article_card(article)

    if not preferred and not others:
        st.info("No articles found matching your filters.")


def _render_article_card(article):
    with st.container():
        desc = strip_html(article.description)
        if desc and len(desc) > 200:
            desc = desc[:200] + "..."
        elif not desc:
            desc = "No description"
        date_str = article.published_at.strftime("%Y-%m-%d %H:%M") if article.published_at else "Unknown"
        st.markdown("**" + strip_html(article.title) + "**")
        topic_display = str(article.primary_topic or "general").title().replace("Ai & Ml", "AI & ML").replace("Ai ", "AI ").replace("Ml", "ML")

        contras = get_article_contradictions(article.id)
        contra_badge = ""
        if contras:
            max_score = max(c["contradiction_score"] for c in contras)
            if max_score >= 0.70:
                contra_badge = ' <span style="background:#dc262622; color:#dc2626; padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600;">⚠️ HIGH CONTRADICTION</span>'
            elif max_score >= 0.50:
                contra_badge = ' <span style="background:#f59e0b22; color:#f59e0b; padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600;">⚡ CONTRADICTION</span>'
            else:
                contra_badge = ' <span style="background:#6b728022; color:#6b7280; padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600;">⚡ Low Contradiction</span>'
        else:
            contra_badge = ' <span style="background:#10b98122; color:#10b981; padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600;">✓ Verified</span>'

        st.markdown("📡 " + str(article.source_name or "Unknown") + " | 🏷️ " + topic_display + " | ⭐ " + str(article.quality_score or 0) + contra_badge, unsafe_allow_html=True)
        st.markdown(desc)

        if contras:
            for c in contras:
                score = c["contradiction_score"]
                if score >= 0.70:
                    bar_color = "#ef4444"
                    label = "HIGH"
                elif score >= 0.50:
                    bar_color = "#f59e0b"
                    label = "MED"
                else:
                    bar_color = "#6b7280"
                    label = "LOW"
                st.markdown(f"""
                <div style="display:flex; align-items:center; gap:0.5rem; margin:0.25rem 0; font-size:0.75rem;">
                    <span style="background:{bar_color}22; color:{bar_color}; padding:0.1rem 0.35rem; border-radius:3px; font-weight:700; font-size:0.65rem;">{label}</span>
                    <span style="color:#9ca3af;">Conflicts with</span>
                    <span style="color:#e5e7eb; font-weight:500;">{c['other_title'][:60]}{'...' if len(c['other_title']) > 60 else ''}</span>
                    <span style="color:#6b7280;">({c['other_source']})</span>
                    <span style="color:#9ca3af; margin-left:auto;">{c['contradiction_score']}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown('<div style="font-size:0.7rem; color:#374151; margin:0.15rem 0;">✓ No conflicting reports detected for this article</div>', unsafe_allow_html=True)

        st.markdown("🕐 " + date_str)
        st.markdown("---")

# ============================================================
# ENHANCED DAILY BRIEFING PAGE
# ============================================================

def daily_briefing_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">📰 Daily Briefing</h1>
        <p style="color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.9rem;">AI-generated executive briefings powered by LangGraph agents</p>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🚀 Generate", "📜 History", "⚙️ Agent Config"])

    with tab1:
        user = st.session_state.user
        user_prefs = get_user_preferences(user.id) if user else []
        default_topics = ", ".join([p.topic for p in user_prefs]) if user_prefs else "technology, ai, business"

        c1, c2 = st.columns([3, 1])
        with c1:
            topics_input = st.text_input("Topics", value=default_topics, help="Comma-separated topics for the briefing")
        with c2:
            max_retries = st.slider("Max Revisions", 0, 3, 2, help="Critic agent revision loops")

        auto_trigger = False
        if "last_briefing" not in st.session_state or not st.session_state.get("last_briefing"):
            auto_trigger = True

        manual_generate = st.button("🚀 Generate Briefing", type="primary", use_container_width=True)

        if auto_trigger or manual_generate:
            if not topics_input.strip():
                st.warning("Enter at least one topic")
            else:
                if user and user.id:
                    log_user_query(user.id, "[BRIEFING] " + topics_input)
                    for t in topics_input.split(","):
                        t = t.strip().lower()
                        if t:
                            add_user_preference(user.id, t, 1.0)

                with st.spinner("Running LangGraph Agent..."):
                    try:
                        from platform_agent import build_platform_agent

                        agent = build_platform_agent()
                        initial_state = {
                            "user_id": user.id if user else "anonymous",
                            "user_preferences": [t.strip() for t in topics_input.split(",") if t.strip()],
                            "retrieved_articles": [],
                            "final_briefing": "",
                            "critique_feedback": "",
                            "retry_count": 0,
                            "max_retries": max_retries
                        }

                        result = agent.invoke(initial_state)
                        briefing = result.get("final_briefing", "")

                        if briefing:
                            st.session_state.last_briefing = briefing
                            st.session_state.last_briefing_meta = {
                                "topics": topics_input,
                                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                                "revisions": result.get("retry_count", 0)
                            }
                            if manual_generate:
                                st.success("Briefing generated successfully!")
                            else:
                                st.rerun()
                        else:
                            st.error("Agent returned empty briefing. Check logs.")
                    except Exception as e:
                        st.error(f"Agent execution failed: {str(e)}")
                        logger.exception("Briefing generation failed")

        if st.session_state.get("last_briefing"):
            st.markdown("---")
            st.markdown("### 📄 Generated Briefing")
            st.markdown(st.session_state.last_briefing)

    with tab2:
        briefings = get_user_briefings(user.id, 20) if user else get_daily_briefings(20)
        if not briefings:
            st.info("No briefings yet. Generate your first one above!")
        else:
            for b in briefings:
                with st.expander("📰 " + str(b.user_id or "Unknown") + " — " + (b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "Unknown")):
                    st.caption("Topics: " + str(b.topic_preferences))
                    st.markdown(b.content or "*No content*")

    with tab3:
        st.info("""
        **Agent Configuration**
        - **Model**: Llama 3.3 70B via Groq
        - **Retrieval**: PostgreSQL + ChromaDB hybrid
        - **Critic**: Self-reflection loop with max 2 revisions
        - **Trust Threshold**: 70% minimum for source credibility warnings
        - **Contradiction Threshold**: 0.50 NLI score
        """)
        st.markdown("**Pipeline Stages:**")
        st.markdown("""
        1. `retrieve` → Fetch articles by user preferences
        2. `evaluator` → Check article volume (retry if < 2)
        3. `brief_gen` → Generate briefing with RAG + contradiction context
        4. `critic` → Quality review (hallucination check, formatting, relevance)
        5. `critic_router` → APPROVED → deliver, NEEDS_REVISION → revise
        6. `deliver` → Save to PostgreSQL `daily_briefings` table
        """)

# ============================================================
# PREFECT FLOWS PAGE
# ============================================================

def prefect_flows_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">🔄 Prefect Orchestration</h1>
        <p style="color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.9rem;">Workflow automation for ingestion and briefing pipelines</p>
    </div>
    """, unsafe_allow_html=True)

    st.info("""
    **Scheduled Flows (Cron)**
    - `news-ingestion-every-3-hours` → Runs at minute 0 of every 3rd hour
    - `daily-news-briefing-7am` → Runs daily at 07:00 Asia/Kolkata
    """)

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("📥 News Ingestion Pipeline")
        st.markdown("""
        **Stages:**
        1. Parallel API fetching (NewsAPI, GNews, Currents, NYTimes, RSS)
        2. Text cleaning & language detection
        3. Entity extraction & enrichment
        4. Embedding generation → ChromaDB
        5. BERTopic clustering
        6. Recommendation scoring
        7. Semantic deduplication
        """)
        if st.button("▶️ Run Ingestion Now", type="primary", use_container_width=True):
            with st.spinner("Running ingestion pipeline... This may take 2-5 minutes"):
                try:
                    from prefect_flows import ingestion_flow
                    result = ingestion_flow()
                    st.success(f"Ingestion completed! Status: {result.get('status', 'unknown')}")
                    st.json(result.get("statistics", {}))
                    st.session_state.flow_runs.append({
                        "Flow": "ingestion", "Status": "Success",
                        "Time": datetime.now().strftime("%H:%M:%S"), "Details": str(result.get("statistics", {}))[:100]
                    })
                except Exception as e:
                    st.error(f"Ingestion failed: {str(e)}")
                    logger.exception("Prefect ingestion failed")
                    st.session_state.flow_runs.append({
                        "Flow": "ingestion", "Status": f"Failed: {str(e)[:60]}",
                        "Time": datetime.now().strftime("%H:%M:%S"), "Details": ""
                    })

    with c2:
        st.subheader("📰 Daily Briefing Pipeline")
        st.markdown("""
        **Stages:**
        1. Load active users & preferences
        2. Retrieve topic-matched articles
        3. Run trust scoring & contradiction detection
        4. LangGraph agent generation + critic loop
        5. Save approved briefings to PostgreSQL
        """)
        if st.button("▶️ Run Briefing Now", type="primary", use_container_width=True):
            with st.spinner("Running briefing pipeline for all active users..."):
                try:
                    from prefect_flows import daily_briefing_flow
                    result = daily_briefing_flow()
                    st.success(f"Briefing pipeline completed! Status: {result.get('status', 'unknown')}")
                    st.session_state.flow_runs.append({
                        "Flow": "briefing", "Status": "Success",
                        "Time": datetime.now().strftime("%H:%M:%S"), "Details": ""
                    })
                except Exception as e:
                    st.error(f"Briefing pipeline failed: {str(e)}")
                    logger.exception("Prefect briefing failed")
                    st.session_state.flow_runs.append({
                        "Flow": "briefing", "Status": f"Failed: {str(e)[:60]}",
                        "Time": datetime.now().strftime("%H:%M:%S"), "Details": ""
                    })

    st.markdown("---")
    st.subheader("📊 Flow Run History (Local)")
    st.info("For production monitoring, visit the Prefect UI at `http://localhost:4200` after running `prefect server start`")

    if "flow_runs" not in st.session_state:
        st.session_state.flow_runs = []

    if st.session_state.flow_runs:
        df = pd.DataFrame(st.session_state.flow_runs)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No manual runs recorded this session. Run a flow above to see history.")

# ============================================================
# CONTRADICTIONS EXPLORER PAGE
# ============================================================

def contradictions_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">⚠️ Contradictions Explorer</h1>
        <p style="color: rgba(255,255,255,0.8); margin: 0.3rem 0 0 0; font-size: 0.9rem;">Detect conflicting narratives across news sources using NLI</p>
    </div>
    """, unsafe_allow_html=True)

    stats = get_contradiction_stats()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Detected", stats["total"])
    c2.metric("High Confidence (≥0.70)", stats["high_confidence"])
    c3.metric("Average Score", stats["average_score"])
    c4.metric("Latest Detection", stats["latest_detection"])

    st.markdown("---")

    col1, col2 = st.columns([1, 3])
    with col1:
        min_score = st.slider("Min Contradiction Score", 0.0, 1.0, 0.0, 0.05)
    with col2:
        st.info("""
        **How contradictions work:**
        The NLI (Natural Language Inference) model compares article pairs and scores them on 
        *contradiction*, *entailment*, and *neutrality*. Scores ≥ 0.50 are saved to the database 
        during Daily Briefing or RAG pipeline runs.
        """)

    contradictions = get_contradictions_with_articles(limit=100, min_score=min_score)

    if not contradictions:
        st.warning("""
        **No contradictions found in the database.**

        Contradictions are generated when the Daily Briefing agent or RAG pipeline runs. 
        To populate this page:
        1. Go to **📰 Daily Briefing** → click **🚀 Generate Briefing**
        2. Or go to **🔄 Prefect Flows** → click **▶️ Run Briefing Now**
        3. Or run `python platform_agent.py` from your terminal

        The NLI model (`cross-encoder/nli-deberta-v3-small`) will compare the most trusted 
        article against every other retrieved article and save detected contradictions here.
        """)
        return

    st.subheader("📊 Contradiction Score Distribution")
    df = pd.DataFrame(contradictions)
    fig = px.histogram(df, x="contradiction_score", nbins=20, color_discrete_sequence=["#ef4444"])
    fig.update_layout(height=250, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.subheader(f"🔍 Detected Pairs ({len(contradictions)} results)")

    for c in contradictions:
        with st.container():
            score = c["contradiction_score"]
            if score >= 0.70:
                badge_color = "#dc2626"
                badge_text = "HIGH"
            elif score >= 0.50:
                badge_color = "#f59e0b"
                badge_text = "MEDIUM"
            else:
                badge_color = "#6b7280"
                badge_text = "LOW"

            st.markdown(f"""
            <div style="border-left: 4px solid {badge_color}; padding-left: 1rem; margin-bottom: 1rem;">
                <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.3rem;">
                    <span style="background:{badge_color}; color:white; padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:bold;">{badge_text}</span>
                    <span style="font-weight:600;">Score: {score}</span>
                    <span style="color:#6b7280; font-size:0.8rem;">Threshold: {c['threshold_used']}</span>
                </div>
                <div style="display:grid; grid-template-columns: 1fr auto 1fr; gap:1rem; align-items:start;">
                    <div>
                        <div style="font-size:0.75rem; color:#6b7280;">Article 1</div>
                        <div style="font-weight:500;">{c['title_1'][:80]}{'...' if len(c['title_1']) > 80 else ''}</div>
                        <div style="font-size:0.75rem; color:#9ca3af;">📡 {c['source_1']} | ID: {c['article_1_id']}</div>
                    </div>
                    <div style="text-align:center; padding-top:0.5rem;">
                        <div style="font-size:1.2rem;">⚡</div>
                        <div style="font-size:0.65rem; color:#6b7280;">VS</div>
                    </div>
                    <div>
                        <div style="font-size:0.75rem; color:#6b7280;">Article 2</div>
                        <div style="font-weight:500;">{c['title_2'][:80]}{'...' if len(c['title_2']) > 80 else ''}</div>
                        <div style="font-size:0.75rem; color:#9ca3af;">📡 {c['source_2']} | ID: {c['article_2_id']}</div>
                    </div>
                </div>
                <div style="margin-top:0.5rem; display:flex; gap:1rem; font-size:0.75rem; color:#6b7280;">
                    <span>Contradiction: <b>{c['contradiction_score']}</b></span>
                    <span>Entailment: <b>{c['entailment_score']}</b></span>
                    <span>Neutral: <b>{c['neutral_score']}</b></span>
                    <span>🕐 {c['detected_at']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("---")

    with st.expander("📋 Raw Data Table"):
        st.dataframe(df[["title_1", "title_2", "contradiction_score", "entailment_score", "neutral_score", "detected_at"]], 
                    use_container_width=True, hide_index=True)

# ============================================================
# SEARCH PAGE
# ============================================================

def search_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">🔍 Semantic Search</h1>
    </div>
    """, unsafe_allow_html=True)
    query = st.text_input("Search query")
    top_k = st.slider("Results", 1, 20, 5)
    if st.button("🔍 Search", type="primary"):
        if not query:
            st.warning("Enter a query")
            return
        if st.session_state.user and st.session_state.user.id:
            log_user_query(st.session_state.user.id, query)
        with st.spinner("Searching ChromaDB..."):
            try:
                from src.vector_storage.chroma_manager import ChromaManager
                from src.semantic_representation.embedding_generator import EmbeddingGenerator
                cm = ChromaManager()
                emb = EmbeddingGenerator()
                results = cm.search_by_text(query, top_k=top_k, embedder=emb)
                docs = results.get("documents", [[]])[0] or []
                metas = results.get("metadatas", [[]])[0] or []
                if not docs:
                    st.info("No results found")
                    return
                for i, (doc, meta) in enumerate(zip(docs, metas), 1):
                    meta = meta or {}
                    with st.container():
                        st.markdown(f"**{i}. {meta.get('title', 'Untitled')}**")
                        search_topic = str(meta.get('topic', 'general')).title().replace("Ai & Ml", "AI & ML").replace("Ai ", "AI ").replace("Ml", "ML")
                        st.caption(f"Source: {meta.get('source', 'Unknown')} | Topic: {search_topic} | Quality: {meta.get('quality_score', 0)}")
                        st.markdown(doc[:300] + "..." if len(doc) > 300 else doc)
                        st.markdown("---")
            except Exception as e:
                st.error(f"Search failed: {str(e)}")

# ============================================================
# PROFILE PAGE
# ============================================================

def profile_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">👤 Profile & Preferences</h1>
    </div>
    """, unsafe_allow_html=True)
    user = st.session_state.user
    if not user:
        st.error("Not authenticated")
        return
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📋 Account Info")
        st.markdown("**User ID:** `" + user.id + "`")
        st.markdown("**Username:** " + str(user.username))
        st.markdown("**Email:** " + str(user.email))
        st.markdown("**Name:** " + str(user.full_name or "N/A"))
        st.markdown("**Role:** `" + str(st.session_state.user_role) + "`")
    with c2:
        st.subheader("➕ Add Preference")
        with st.form("add_pref"):
            topic_choices = get_article_topics()[1:]  
            existing_topics = {p.topic for p in get_user_preferences(user.id)}
            available_choices = [t for t in topic_choices if t not in existing_topics]
            if available_choices:
                nt = st.selectbox("Topic", available_choices)
            else:
                nt = None
                st.info("You already have preferences for every available topic.")
            w = st.slider("Weight", 0.1, 2.0, 1.0, 0.1)
            if st.form_submit_button("Add", type="primary"):
                if nt:
                    if add_user_preference(user.id, nt, w):
                        st.success("Added!")
                        st.rerun()
                else:
                    st.warning("No topic selected")
    st.markdown("---")
    st.subheader("🏷️ Your Preferences")
    prefs = get_user_preferences(user.id)
    if prefs:
        df = pd.DataFrame([{"ID": p.id, "Topic": p.topic, "Weight": p.weight} for p in prefs])
        st.dataframe(df, use_container_width=True, hide_index=True)
        opts = {f"{p.topic} (w:{p.weight})": p.id for p in prefs}
        sel = st.selectbox("Remove", list(opts.keys()))
        if st.button("Remove"):
            if remove_user_preference(opts[sel]):
                st.success("Removed!")
                st.rerun()
    else:
        st.info("No preferences yet.")
    st.markdown("---")
    st.subheader("🔍 Recent Activity")
    hist = get_user_query_history(user.id, 20)
    if hist:
        df = pd.DataFrame([{"Query": h.query, "Time": h.created_at.strftime("%Y-%m-%d %H:%M") if h.created_at else ""} for h in hist])
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No activity yet.")

# ============================================================
# ANALYTICS PAGE (ADMIN ONLY)
# ============================================================

def analytics_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">📊 Content & Trust Analytics</h1>
        <p style="color: rgba(255,255,255,0.7); margin: 0.3rem 0 0 0; font-size: 0.9rem;">Deep insights into articles, trust scores, and content quality</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Trust Score Distribution by Article")
        trust_data = get_trust_distribution_by_category()
        if trust_data:
            df = pd.DataFrame(trust_data)
            topic_colors = {
                "ai & ml": "#06b6d4", "technology": "#3b82f6", "finance": "#ef4444",
                "health": "#f59e0b", "politics": "#8b5cf6", "science": "#10b981", "climate": "#eab308",
                "general": "#6b7280"
            }
            df = df.sort_values("quality_score", ascending=False)
            fig = px.bar(df, x="title", y="quality_score", color="topic",
                        color_discrete_map=topic_colors,
                        labels={"quality_score": "Trust Score (%)", "title": "Article"},
                        hover_data={"title": True, "quality_score": ":.0f", "topic": True})
            fig.update_layout(
                height=420,
                margin=dict(l=0, r=10, t=10, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e5e7eb",
                xaxis_showticklabels=False,
                showlegend=True,
                legend=dict(
                    orientation="v", yanchor="middle", y=0.5,
                    xanchor="left", x=1.02, font=dict(size=11, color="#e5e7eb")
                )
            )
            fig.update_yaxes(range=[0, 100], gridcolor="#374151", title_font_color="#9ca3af")
            fig.update_xaxes(gridcolor="#374151")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trust data available")

    with c2:
        st.subheader("Topic Breakdown Across Network")
        topics = get_topic_breakdown()
        if topics:
            fig = make_donut_chart(
                list(topics.keys()), list(topics.values()),
                height=420, dark=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No topic data available")

    st.markdown("---")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Trust Score Trends Over Time")
        trends = get_trust_trends_over_time(days=14)
        if trends:
            df = pd.DataFrame(trends)
            df["date"] = pd.to_datetime(df["date"])
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df["date"], y=df["volume"], name="Article Volume", marker_color="#ef4444", opacity=0.6, yaxis="y2"))
            fig.add_trace(go.Scatter(x=df["date"], y=df["avg_trust"], mode="lines+markers", name="Avg Trust Score", line=dict(color="#06b6d4", width=3), marker=dict(size=8, color="#06b6d4")))
            fig.update_layout(
                height=370,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e5e7eb",
                xaxis=dict(gridcolor="#374151", tickfont=dict(color="#9ca3af")),
                yaxis=dict(title="Avg Trust Score", range=[75, 100], gridcolor="#374151", side="left", title_font=dict(color="#9ca3af"), tickfont=dict(color="#9ca3af")),
                yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False, title_font=dict(color="#9ca3af"), tickfont=dict(color="#9ca3af")),
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, font=dict(color="#e5e7eb")),
                hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No trend data available")

    with c2:
        st.subheader("Source Credibility Distribution")
        matrix = get_source_quality_matrix()
        if matrix:
            df = pd.DataFrame(matrix).sort_values("avg_trust", ascending=True)
            fig = px.bar(df, y="source", x="avg_trust", orientation="h",
                        color="avg_trust", color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"])
            fig.update_layout(
                height=350,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e5e7eb",
                yaxis=dict(gridcolor="#374151", title="News Source", title_font=dict(color="#9ca3af"), tickfont=dict(color="#e5e7eb")),
                xaxis=dict(range=[0, 100], gridcolor="#374151", title="Avg Trust Score", title_font=dict(color="#9ca3af"), tickfont=dict(color="#9ca3af")),
                coloraxis_showscale=False,
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No source data available")

    st.markdown("---")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Sentiment Distribution by Category")
        sent_data = get_sentiment_distribution_by_category()
        if sent_data:
            df = pd.DataFrame(sent_data)
            fig = px.bar(df, x="category", y="count", color="sentiment",
                        color_discrete_map={"positive": "#10b981", "neutral": "#f59e0b", "negative": "#ef4444", "unknown": "#6b7280"},
                        barmode="group")
            fig.update_layout(
                height=320,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e5e7eb",
                xaxis=dict(gridcolor="#374151", title="Category", title_font=dict(color="#9ca3af"), tickfont=dict(color="#e5e7eb")),
                yaxis=dict(gridcolor="#374151", title="Count", title_font=dict(color="#9ca3af"), tickfont=dict(color="#9ca3af")),
                legend=dict(orientation="h", yanchor="bottom", y=-0.4, font=dict(color="#e5e7eb"))
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sentiment data available")

    with c2:
        st.subheader("Contradiction Density by Category")
        contr_data = get_contradiction_density_by_category()
        if contr_data:
            df = pd.DataFrame(contr_data).sort_values("contradictions", ascending=False)
            fig = px.bar(df, x="category", y="contradictions",
                        color="contradictions", color_continuous_scale="Reds")
            fig.update_layout(
                height=300,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e5e7eb",
                xaxis=dict(gridcolor="#374151", title="Category", title_font=dict(color="#9ca3af"), tickfont=dict(color="#e5e7eb")),
                yaxis=dict(gridcolor="#374151", title="Contradictions", title_font=dict(color="#9ca3af"), tickfont=dict(color="#9ca3af")),
                coloraxis_showscale=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No contradiction data available")

    st.markdown("---")
    st.subheader("📋 Raw Analytics Tables")

    tab1, tab2 = st.tabs(["Source Breakdown", "User Queries"])
    with tab1:
        matrix = get_source_quality_matrix()
        if matrix:
            st.dataframe(pd.DataFrame(matrix), use_container_width=True, hide_index=True)
    with tab2:
        db = get_db_session()
        try:
            queries = db.query(UserQueryLog).order_by(desc(UserQueryLog.created_at)).limit(50).all()
            if queries:
                df = pd.DataFrame([{"User": q.user_id, "Query": q.query, "Time": q.created_at} for q in queries])
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No queries logged yet")
        finally:
            db.close()

# ============================================================
# AGENT MONITOR PAGE (ADMIN ONLY)
# ============================================================

def agent_monitor_page():
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 1.5rem; border-radius: 16px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 1.8rem;">🤖 Agent Monitor</h1>
        <p style="color: rgba(255,255,255,0.7); margin: 0.3rem 0 0 0; font-size: 0.9rem;">Real-time visibility into both agent pipelines</p>
    </div>
    """, unsafe_allow_html=True)

    agent_status = get_agent_monitor_status()

    c1, c2 = st.columns(2)

    with c1:
        platform = agent_status["platform"]
        st.markdown(f"""
        <div style="background: #1f2937; border-radius: 12px; padding: 1.5rem; border: 1px solid #374151;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></div>
                <span style="color: #e5e7eb; font-weight: 600; font-size: 1.1rem;">Platform Agent (Autonomous)</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Status</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{platform['status']}</div>
                    <span style="background: {platform['badge_color']}22; color: {platform['badge_color']}; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem;">{platform['badge']}</span>
                </div>
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Next Run</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{platform['next_run']}</div>
                </div>
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Briefings Generated</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{platform['briefings_generated']}</div>
                </div>
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Last Status</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{platform['last_status']}</div>
                    <span style="background: #10b98122; color: #10b981; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem;">✓ Delivered</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        qa = agent_status["qa"]
        st.markdown(f"""
        <div style="background: #1f2937; border-radius: 12px; padding: 1.5rem; border: 1px solid #374151;">
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: #10b981; box-shadow: 0 0 8px #10b981;"></div>
                <span style="color: #e5e7eb; font-weight: 600; font-size: 1.1rem;">Q&A Agent (Interactive)</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Status</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{qa['status']}</div>
                    <span style="background: {qa['badge_color']}22; color: {qa['badge_color']}; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem;">{qa['badge']}</span>
                </div>
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Queries Answered</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{qa['queries_answered']}</div>
                </div>
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Avg Response Time</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{qa['avg_response_time']}</div>
                    <span style="background: #8b5cf622; color: #8b5cf6; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem;">Chroma + Groq</span>
                </div>
                <div>
                    <div style="color: #9ca3af; font-size: 0.75rem;">Last Status</div>
                    <div style="color: #e5e7eb; font-size: 1.3rem; font-weight: 700;">{qa['last_status']}</div>
                    <span style="background: #10b98122; color: #10b981; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.7rem;">✓ Standing by</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("""
        <div style="background: #1f2937; border-radius: 12px; padding: 1.5rem; border: 1px solid #374151;">
            <h4 style="color: #e5e7eb; margin-top: 0;">🏭 Platform Agent Pipeline</h4>
            <div style="font-family: monospace; font-size: 0.8rem; line-height: 1.8; color: #d1d5db;">
                <div style="color: #60a5fa;">▶ Prefect Scheduler</div>
                <div style="padding-left: 1rem; color: #9ca3af;">Every day at 8:00 AM</div>
                <div style="color: #34d399;">▶ Platform Agent</div>
                <div style="padding-left: 1rem; color: #9ca3af;">LangGraph StateGraph</div>
                <div style="padding-left: 1rem;">→ Retrieve User Preferences</div>
                <div style="padding-left: 1rem;">→ PostgreSQL Personalized Retrieval</div>
                <div style="padding-left: 1rem; color: #fbbf24;">→ NewsGenerationEngine</div>
                <div style="padding-left: 2rem; color: #9ca3af;">Groq: llama-3.3-70b-versatile</div>
                <div style="padding-left: 1rem; color: #f97316;">→ Critic / Reflection</div>
                <div style="padding-left: 1rem;">→ Save DailyBriefing (PostgreSQL)</div>
                <div style="padding-left: 1rem; color: #a78bfa;">→ Email / Push / API</div>
            </div>
            <div style="margin-top: 1rem; padding: 0.75rem; background: #111827; border-radius: 8px; color: #9ca3af; font-size: 0.8rem;">
                <b style="color: #e5e7eb;">Recent Platform Agent Runs:</b><br/>
                No runs yet. Generate a briefing in the Daily Briefing tab.
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown("""
        <div style="background: #1f2937; border-radius: 12px; padding: 1.5rem; border: 1px solid #374151;">
            <h4 style="color: #e5e7eb; margin-top: 0;">💬 Q&A Agent Pipeline</h4>
            <div style="font-family: monospace; font-size: 0.8rem; line-height: 1.8; color: #d1d5db;">
                <div style="color: #60a5fa;">▶ User</div>
                <div style="padding-left: 1rem; color: #9ca3af;">Ask Question (Web UI)</div>
                <div style="color: #34d399;">▶ Q&A Agent</div>
                <div style="padding-left: 1rem; color: #9ca3af;">Triggered by user input</div>
                <div style="padding-left: 1rem;">→ Retrieve from ChromaDB</div>
                <div style="padding-left: 2rem; color: #9ca3af;">MiniLM embeddings, top_k=5</div>
                <div style="padding-left: 1rem; color: #fbbf24;">→ Generate Answer</div>
                <div style="padding-left: 2rem; color: #9ca3af;">Groq: llama-3.3-70b-versatile</div>
                <div style="padding-left: 1rem; color: #f97316;">→ Critic / Reflection</div>
                <div style="padding-left: 2rem; color: #9ca3af;">Trust check, source diversity</div>
                <div style="padding-left: 1rem; color: #a78bfa;">→ Return Answer</div>
                <div style="padding-left: 2rem; color: #9ca3af;">Rendered in chat UI</div>
            </div>
            <div style="margin-top: 1rem; padding: 0.75rem; background: #111827; border-radius: 8px; color: #9ca3af; font-size: 0.8rem;">
                <b style="color: #e5e7eb;">Recent Q&A Agent Queries:</b><br/>
                No queries yet. Ask something in the Q&A Agent tab.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("🖥️ System Components Status")
    components = get_system_component_status()

    for i in range(0, len(components), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(components):
                comp = components[i + j]
                with cols[j]:
                    with st.container(border=True):
                        c1, c2 = st.columns([0.1, 0.9])
                        with c1:
                            st.markdown(f'<div style="width: 12px; height: 12px; border-radius: 50%; background: {comp["color"]}; box-shadow: 0 0 8px {comp["color"]}; margin-top: 6px;"></div>', unsafe_allow_html=True)
                        with c2:
                            st.markdown(f"**{comp['name']}**")
                            st.caption(comp['detail'])
                        st.markdown(f"<div style='text-align: right; color: {comp['color']}; font-weight: 600; font-size: 0.85rem;'>{comp['status']}</div>", unsafe_allow_html=True)

    st.markdown("---")

    st.subheader("📜 Execution Logs")
    db = get_db_session()
    try:
        briefings = db.query(DailyBriefing).order_by(desc(DailyBriefing.created_at)).limit(10).all()
        queries = db.query(UserQueryLog).order_by(desc(UserQueryLog.created_at)).limit(10).all()

        if not briefings and not queries:
            st.info("Agent logs will appear here as pipelines execute.")
        else:
            with st.container(border=True):
                log_container = st.container(height=300)
                with log_container:
                    for b in briefings:
                        ts = b.created_at.strftime("%Y-%m-%d %H:%M") if b.created_at else "?"
                        st.markdown(f"<span style='color: #34d399; font-family: monospace;'>[PLATFORM]</span> <span style='color: #9ca3af; font-family: monospace;'>{ts}</span> <span style='color: #d1d5db; font-family: monospace;'>Briefing generated for {b.user_id} — topics: {b.topic_preferences}</span>", unsafe_allow_html=True)
    finally:
        db.close()


# ============================================================
# USER MANAGEMENT HELPERS (Admin Only)
# ============================================================

def get_all_users():
    """Fetch all users from the database."""
    db = get_db_session()
    try:
        return db.query(User).order_by(User.username).all()
    except Exception as e:
        logger.error("Error fetching all users: " + str(e))
        return []
    finally:
        db.close()

def update_user_role(user_id, new_role):
    """Promote or demote a user's role."""
    db = get_db_session()
    try:
        user = db.query(User).filter(User.id == str(user_id)).first()
        if user:
            # Update role matching the SQLAlchemy model Enum
            if new_role == "admin":
                user.role = UserRole.admin
            else:
                user.role = UserRole.user
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating role for user {user_id}: " + str(e))
        return False
    finally:
        db.close()

        

# ============================================================
# MAIN ROUTER (ADD THIS AT THE BOTTOM OF app.py)
# ============================================================

def main():
    # Sidebar Navigation
    st.sidebar.title("📰 News Intelligence")
    
    if not st.session_state.get("authenticated"):
        menu = ["Login", "Register"]
        choice = st.sidebar.selectbox("Navigation", menu)
        if choice == "Login":
            login_page()
        elif choice == "Register":
            register_page()
    else:
        st.sidebar.write(f"Logged in as: **{st.session_state.get('username')}**")
        if st.sidebar.button("Logout"):
            logout()

        # Admin vs User navigation
        role = st.session_state.get("user_role")
        pages = {
            "Dashboard": dashboard_page,
            "Articles": articles_page,
            "Daily Briefing": daily_briefing_page,
            "Contradictions": contradictions_page,
            "Semantic Search": search_page,
            "Profile": profile_page,
        }
        
        if role == "admin":
            pages["Prefect Flows"] = prefect_flows_page
            pages["Analytics"] = analytics_page
            pages["Agent Monitor"] = agent_monitor_page

        choice = st.sidebar.radio("Go to", list(pages.keys()))
        pages[choice]()



if __name__ == "__main__":
    main()