import sys
import os
import json
from typing import TypedDict, List, Dict, Any, Literal
from dotenv import load_dotenv
from sqlalchemy import func
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

import re
from difflib import SequenceMatcher

# Load environment variables and project root
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import SessionLocal, engine, Base
# from src.database.models import RawArticles, DailyBriefing, User, UserPreference
from src.database.models import (
    RawArticles,
    DailyBriefing,
    User,
    UserPreference,
    ArticleRecommendation,
)

from src.generation.rag_engine import NewsGenerationEngine

# Ensure tables are created when the agent boots
Base.metadata.create_all(bind=engine)

# generation_engine = NewsGenerationEngine()


# --- 1. Define Agent Memory State ---
class PlatformState(TypedDict):

    user_id: str

    user_preferences: List[str]

    retrieved_articles: List[Dict]

    final_briefing: str

    critique_feedback: str

    retry_count: int

    max_retries: int

    briefing_approved: bool


# --- 2. Define Agent Nodes ---

def data_retrieval_node(state: PlatformState):
    """Pulls articles from PostgreSQL matching preferred topics (case-insensitive)."""
    print(f"📥 RETRIEVAL: Fetching articles for preferences: {state['user_preferences']}...")
    db = SessionLocal()
    
    try:
        lowered_prefs = [p.lower() for p in state["user_preferences"]]
        # articles = (
        #     db.query(RawArticles)
        #     .filter(func.lower(RawArticles.primary_topic).in_(lowered_prefs))
        #     .order_by(RawArticles.published_at.desc())
        #     .limit(5)
        #     .all()
        # )

        # articles = (
        #     db.query(RawArticles, ArticleRecommendation)
        #     .outerjoin(
        #         ArticleRecommendation,
        #         RawArticles.id == ArticleRecommendation.article_id
        #     )
        #     .filter(
        #         func.lower(RawArticles.primary_topic).in_(lowered_prefs)
        #     )
        #     .order_by(RawArticles.published_at.desc())
        #     .limit(5)
        #     .all()
        # )

        articles = (
            db.query(RawArticles, ArticleRecommendation)
            .outerjoin(
                ArticleRecommendation,
                RawArticles.id == ArticleRecommendation.article_id
            )
            .filter(
                func.lower(RawArticles.primary_topic).in_(lowered_prefs),
                RawArticles.preprocessing_status == "completed",
                RawArticles.is_duplicate.is_(False),
            )
            .order_by(
                ArticleRecommendation.recommendation_score.desc().nullslast(),
                RawArticles.published_at.desc(),
            )
            .limit(20)
            .all()
        )

        print("\n📋 RAW QUERY RESULTS:")

        for index, (article, recommendation) in enumerate(articles, 1):
            print(
                f"{index}. {article.title}\n"
                f"   Source: {article.source_name}\n"
                f"   Topic: {article.primary_topic}\n"
                f"   Recommendation: "
                f"{recommendation.recommendation_score if recommendation else None}"
            )

        # taking extra articles insted of 5 so that we can avoid duplicates and same source news

        selected_articles = []
        seen_article_ids = set()
        source_counts = {}

        for article, recommendation in articles:

            # Defense against duplicate join results
            # Skip demo/test data
            demo_keywords = {"demo source", "test source", "mock source"}
            if any(kw in (article.source_name or "").lower() for kw in demo_keywords):
                continue

            #  skip duplicate article IDs (defensive against join artifacts)
            if article.id in seen_article_ids:
                continue

            #  skip if same title already selected (catches same story, different DB rows)
            if article.title in {a[0].title for a in selected_articles}:
                continue

            source = article.source_name or "Unknown"

            # Prefer diversity: maximum 2 stories from one source
            if source_counts.get(source, 0) >= 2:
                continue

            selected_articles.append(
                (article, recommendation)
            )

            seen_article_ids.add(article.id)

            source_counts[source] = (
                source_counts.get(source, 0) + 1
            )

            if len(selected_articles) == 5:
                break
            
        # formatted_articles = [
        #     {
        #         "article_id": art.id,
        #         "title": art.title,
        #         "text": art.cleaned_content or art.description or "",
        #         "source": art.source_name,
        #         "topic": art.primary_topic
        #     }
        #     for art in articles
        # ]

        formatted_articles = [
            {
                "article_id": article.id,
                "title": article.title,
                "text": article.cleaned_content or article.description or "",
                "content": article.cleaned_content or article.content or "",
                "description": article.description,
                "source": article.source_name,
                "topic": article.primary_topic,
                "url": article.url,
                "published_at": article.published_at,
                "author": article.author,
                "quality_score": article.quality_score,

                # Recommendation values
                "trust_score": (
                    recommendation.trust_score
                    if recommendation else None
                ),

                "recommendation_score": (
                    recommendation.recommendation_score
                    if recommendation else None
                ),

                "confidence_score": (
                    recommendation.confidence_score
                    if recommendation else None
                ),

                "freshness_score": (
                    recommendation.freshness_score
                    if recommendation else None
                ),

                "interest_score": (
                    recommendation.interest_score
                    if recommendation else None
                ),
            }
            for article, recommendation in selected_articles
        ]
        
        print(f"   -> Retrieved {len(formatted_articles)} topic-matched articles.")
        print("\n   📊 TOP RETRIEVED ARTICLES:")

        for i, selected_articles in enumerate(formatted_articles, 1):
            print(
                f"   {i}. {selected_articles['title']}\n"
                f"      Topic: {selected_articles['topic']}\n"
                f"      Source: {selected_articles['source']}\n"
                f"      Recommendation: {selected_articles.get('recommendation_score')}\n"
                f"      Trust: {selected_articles.get('trust_score')}\n"
                f"      Freshness: {selected_articles.get('freshness_score')}\n"
            )
        formatted_articles = detect_conflicts(formatted_articles)
        return {"retrieved_articles": formatted_articles}
        
    except Exception as e:
        print(f"❌ Retrieval Error: {e}")
        return {"retrieved_articles": []}
    finally:
        db.close()


def retry_retrieval_node(state: PlatformState):
    """
    Fallback retrieval.

    Keeps the user's topic preferences but broadens the candidate pool.
    It does NOT drop topic constraints, preventing unrelated stories
    from entering a personalized briefing.
    """

    print(
        "🔁 RETRY RETRIEVAL: Broadening candidate pool "
        "while preserving user preferences..."
    )

    db = SessionLocal()

    try:

        lowered_prefs = [
            p.lower()
            for p in state["user_preferences"]
        ]

        # Retrieve a larger candidate pool while STILL
        # respecting the user's preferred topics.
        articles = (
            db.query(
                RawArticles,
                ArticleRecommendation
            )
            .outerjoin(
                ArticleRecommendation,
                RawArticles.id == ArticleRecommendation.article_id
            )
            .filter(
                func.lower(RawArticles.primary_topic).in_(lowered_prefs),
                RawArticles.preprocessing_status == "completed",
                RawArticles.is_duplicate.is_(False),
            )
            .order_by(
                ArticleRecommendation.recommendation_score.desc().nullslast(),
                RawArticles.published_at.desc(),
            )
            .limit(50)
            .all()
        )

        print(
            f"   -> Fallback candidate pool: "
            f"{len(articles)} rows."
        )

        selected_articles = []

        seen_article_ids = set()
        source_counts = {}

        for article, recommendation in articles:

            # Avoid duplicate article IDs
            demo_keywords = {"demo source", "test source", "mock source"}
            if any(kw in (article.source_name or "").lower() for kw in demo_keywords):
                continue

            source = article.source_name or "Unknown"

            # Maintain source diversity
            if source_counts.get(source, 0) >= 2:
                continue

            selected_articles.append(
                (article, recommendation)
            )

            seen_article_ids.add(article.id)

            source_counts[source] = (
                source_counts.get(source, 0) + 1
            )

            if len(selected_articles) == 5:
                break

        formatted_articles = [
            {
                "article_id": article.id,
                "title": article.title,

                "text":
                    article.cleaned_content
                    or article.description
                    or "",

                "content":
                    article.cleaned_content
                    or article.content
                    or "",

                "description": article.description,
                "source": article.source_name,
                "topic": article.primary_topic,
                "url": article.url,
                "published_at": article.published_at,
                "author": article.author,
                "quality_score": article.quality_score,

                "trust_score": (
                    recommendation.trust_score
                    if recommendation
                    else None
                ),

                "recommendation_score": (
                    recommendation.recommendation_score
                    if recommendation
                    else None
                ),

                "confidence_score": (
                    recommendation.confidence_score
                    if recommendation
                    else None
                ),

                "freshness_score": (
                    recommendation.freshness_score
                    if recommendation
                    else None
                ),

                "interest_score": (
                    recommendation.interest_score
                    if recommendation
                    else None
                ),

                "source_preference_score": (
                    recommendation.source_preference_score
                    if recommendation
                    else None
                ),
            }

            for article, recommendation
            in selected_articles
        ]

        print(
            f"   -> Fallback retrieval returned "
            f"{len(formatted_articles)} preference-matched articles."
        )

        print("\n   📊 FALLBACK RETRIEVED ARTICLES:")

        for i, article in enumerate(
            formatted_articles,
            1
        ):

            print(
                f"   {i}. {article['title']}\n"
                f"      Topic: {article['topic']}\n"
                f"      Source: {article['source']}\n"
                f"      Recommendation: "
                f"{article.get('recommendation_score')}"
            )

        return {
            "retrieved_articles":
                formatted_articles,

            "retry_count":
                state.get("retry_count", 0) + 1,
        }

    except Exception as e:

        print(
            f"❌ Retry Retrieval Error: {e}"
        )

        return {
            "retrieved_articles": [],

            "retry_count":
                state.get("retry_count", 0) + 1,
        }

    finally:

        db.close()

def evaluator_node(state: PlatformState) -> Literal["brief_gen", "retry", "end_pipeline"]:
    """Evaluates whether retrieved article volume is sufficient before attempting generation."""
    print("🧐 EVALUATOR: Checking dataset volume...")
    articles = state.get("retrieved_articles", [])
    retry_count = state.get("retry_count", 0)
    
    if len(articles) >= 2:
        print(f"   -> {len(articles)} articles found. Proceeding to Brief Generation.")
        return "brief_gen"

    if retry_count < 1:
        print(f"   -> Only {len(articles)} article(s) found. Broadening retrieval...")
        return "retry"
        
    print(f"   -> Insufficient articles after fallback. Terminating pipeline.")
    return "end_pipeline"


def detect_conflicts(articles: list) -> list:
    NEGATION_WORDS = {"not", "no", "never", "does not", "doesn't", "won't", "cannot", "can't"}

    def normalise(title):
        t = title.lower()
        for neg in sorted(NEGATION_WORDS, key=len, reverse=True):
            t = re.sub(r"\b" + re.escape(neg) + r"\b", "", t)
        return re.sub(r"\s+", " ", t).strip()

    def has_negation(title):
        t = title.lower()
        return any(re.search(r"\b" + re.escape(neg) + r"\b", t) for neg in NEGATION_WORDS)

    for i, a in enumerate(articles):
        a.setdefault("conflict", False)
        a.setdefault("conflict_note", "")
        for j, b in enumerate(articles):
            if i >= j:
                continue
            sim = SequenceMatcher(None, normalise(a.get("title", "")), normalise(b.get("title", ""))).ratio()
            if sim >= 0.70 and (has_negation(a.get("title", "")) != has_negation(b.get("title", ""))):
                note = (
                    f"CONFLICTING REPORTS: '{a['title']}' (source: {a['source']}) "
                    f"contradicts '{b['title']}' (source: {b['source']}). "
                    "Present both sides. Do not resolve without evidence."
                )
                a["conflict"] = True
                b["conflict"] = True
                a["conflict_note"] = note
                b["conflict_note"] = note
    return articles



def brief_gen_node(state: PlatformState):
    """Synthesizes or revises the daily briefing using Groq Llama 3.3.
    Incorporates critique_feedback if returning from a revision loop."""
    print("✍️  GENERATOR: Synthesizing daily briefing...")

    articles = state.get("retrieved_articles", [])
    preferences = state.get("user_preferences", [])
    feedback = state.get("critique_feedback", "")

    print("✍️ GENERATOR: Generating briefing...")

    db = SessionLocal()

    try:

        generation_engine = NewsGenerationEngine(db=db)

        briefing = generation_engine.generate_briefing(

            question=(
                "Generate a personalized daily news briefing for preferences: "
                f"{', '.join(preferences)}.\n\n"
                "STRICT RULES:\n"
                "1. Every fact, name, company, and event MUST appear in the TITLE or "
                "TEXT of the supplied articles. Do NOT add anything from your training data.\n"
                "2. Cover each story ONCE. Do not repeat the same event.\n"
                "3. For any article flagged as conflicting, present BOTH sides clearly. "
                "Do NOT pick a winner or fabricate a resolution.\n"
                "4. Do NOT force unrelated stories into one narrative.\n\n"
                + (
                    "CONFLICTING REPORTS IN THIS BATCH:\n"
                    + "\n".join(dict.fromkeys(
                        a["conflict_note"] for a in articles if a.get("conflict_note")
                    ))
                    + "\n\n"
                    if any(a.get("conflict") for a in articles) else ""
                )
            ),

            retrieved_articles=state["retrieved_articles"],

            critique_feedback=feedback,

        )

        return {
            "final_briefing": briefing
        }

    except Exception as e:

        print(f"Generator Error: {e}")

        return {
            "final_briefing": ""
        }

    finally:

        db.close()

#     context = "\n\n".join([
#         f"Title: {a['title']}\nSource: {a['source']}\nContent: {a['text']}" 
#         for a in articles
#     ])

#     llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0.2)

#     prompt = f"""You are an expert news editor creating a concise daily briefing.

# USER PREFERENCES: {', '.join(preferences)}

# SOURCE ARTICLES:
# {context}

# INSTRUCTIONS:
# - Generate a well-structured, engaging daily briefing in Markdown format.
# - Base facts strictly on the provided articles. Do NOT hallucinate.
# - Ensure key highlights, trends, and source mentions are clear.
# """

#     if feedback:
#         print(f"   -> Applying Critic Feedback to revise briefing: '{feedback}'")
#         prompt += f"\n\nCRITIC FEEDBACK FROM PREVIOUS DRAFT:\n{feedback}\n\nPlease fix the issues highlighted above in your revised draft."

#     try:
#         response = llm.invoke(prompt)
#         print("   -> Briefing generated/revised successfully.")
#         return {"final_briefing": response.content}
#     except Exception as e:
#         print(f"❌ Generator Error: {e}")
#         return {"final_briefing": ""}


def critic_node(state: PlatformState):
    """Self-Reflection / Critic Agent: Inspects the generated draft for hallucinations,
    completeness, and topic relevance before allowing delivery."""
    print("🧐 CRITIC NODE: Evaluating draft briefing quality...")

    briefing = state.get("final_briefing", "")
    articles = state.get("retrieved_articles", [])
    preferences = state.get("user_preferences", [])
    retry_count = state.get("retry_count", 0)

    if not briefing:
        print("   -> Draft is empty. Requesting revision.")
        return {
            "critique_feedback": "Draft was empty.",
            "retry_count": retry_count + 1,
            "briefing_approved": False,
        }

    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

    article_titles = "\n".join(
        f"{i}. {article.get('title', 'Untitled')}"
        for i, article in enumerate(articles, 1)
    )

    prompt = f"""You are a strict Quality Control Editor reviewing a daily news briefing.

USER PREFERENCES: {', '.join(preferences)}
SOURCE ARTICLES COUNT: {len(articles)}

RETRIEVED ARTICLE TITLES:
{article_titles}

DRAFT BRIEFING TO EVALUATE:
{briefing}

EVALUATION CRITERIA:

1. Does the briefing align with the user's requested preferences?

2. Does it cover the important DISTINCT stories from the retrieved articles?

3. Does it avoid repeatedly discussing the same article or same event?

4. Does each major story receive a concise and useful summary?

5. Does it avoid forcing unrelated stories into one narrative?

6. Is the formatting clean, professional, and suitable for a daily news briefing?

7. Does it stay grounded in the supplied articles without hallucinating?

8. Are trust or contradiction warnings only presented when actually warranted?

# 9.Do not require every retrieved article to appear in the briefing. Articles that are clearly irrelevant, incorrectly classified, redundant, or lower-value may be omitted. Evaluate whether the briefing covers the most relevant distinct stories available.

Respond STRICTLY in JSON format with two keys:
{{
    "status": "APPROVED" or "NEEDS_REVISION",
    "feedback": "Concise explanation of what needs fixing if rejected, or 'Looks good' if approved."
}}
"""

    try:
        response = llm.invoke(prompt)
        content = response.content.strip()
        
        # Clean Markdown JSON backticks if returned
        if content.startswith("```json"):
            content = content[7:-3].strip()
        elif content.startswith("```"):
            content = content[3:-3].strip()

        review = json.loads(content)
        status = review.get("status", "APPROVED")
        feedback = review.get("feedback", "")

        print(f"   -> Critic Decision: {status}")
        if feedback:
            print(f"   -> Critic Feedback: {feedback}")

        if status == "APPROVED":

            return {
                "critique_feedback": "",
                "retry_count": retry_count,
                "briefing_approved": True,
            }

        else:

            return {
                "critique_feedback": feedback,
                "retry_count": retry_count + 1,
                "briefing_approved": False,
            }

    except Exception as e:

        print(
            f"⚠️ Critic evaluation error: {e}"
        )

        return {
            "critique_feedback":
                "Critic evaluation failed.",

            "retry_count":
                state.get("max_retries", 2),

            "briefing_approved":
                False,
        }


def critic_router(state: PlatformState) -> Literal["deliver", "revise", "end_pipeline"]:
    """Conditional router for the Critic's decision."""
    feedback = state.get("critique_feedback", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)

    # Safety cap against infinite revision loops
    # if retry_count >= max_retries:
    #     print(f"   -> Max retries ({max_retries}) reached. Proceeding to delivery.")
    #     return "deliver"

    if retry_count >= max_retries:
        if state.get("final_briefing"):
            print(
                f"   -> Max retries ({max_retries}) reached. "
                "Delivering best available draft with quality warning."
            )
            return "deliver"
        else:
            print(f"   -> Max retries ({max_retries}) reached and no draft exists. Terminating.")
            return "end_pipeline"

    if feedback:
        return "revise"
    
    return "deliver"


def delivery_node(state: PlatformState):
    """Saves the approved daily briefing to the PostgreSQL daily_briefings table."""
    print("🚀 DELIVERY: Saving approved briefing to PostgreSQL database...")

    if not state.get("final_briefing"):
        print("   ⚠️ No valid briefing available. Skipping database save.")
        return state

    db = SessionLocal()
    try:
        new_briefing = DailyBriefing(
            user_id=state.get("user_id", "unknown_user"),
            topic_preferences=",".join(state.get("user_preferences", [])),
            content=state.get("final_briefing", "")
        )
        db.add(new_briefing)
        db.commit()
        print("   -> Briefing successfully saved to PostgreSQL ('daily_briefings' table)!")
    except Exception as e:
        db.rollback()
        print(f"❌ Database Save Error: {e}")
    finally:
        db.close()

    return state


# --- 3. Wire the Agentic LangGraph Graph ---
def build_platform_agent():
    builder = StateGraph(PlatformState)

    # Register nodes
    builder.add_node("retrieve", data_retrieval_node)
    builder.add_node("retry_retrieve", retry_retrieval_node)
    builder.add_node("brief_gen", brief_gen_node)
    builder.add_node("critic", critic_node)
    builder.add_node("deliver", delivery_node)

    # Edges
    builder.add_edge(START, "retrieve")

    # Initial Retrieval Evaluation
    builder.add_conditional_edges("retrieve", evaluator_node, {
        "brief_gen": "brief_gen",
        "retry": "retry_retrieve",
        "end_pipeline": END
    })

    # Retry Retrieval Evaluation
    builder.add_conditional_edges("retry_retrieve", evaluator_node, {
        "brief_gen": "brief_gen",
        "retry": "retry_retrieve",
        "end_pipeline": END
    })

    # Generator -> Critic
    builder.add_edge("brief_gen", "critic")

    # Critic -> Dynamic Router (Reflection Loop)
    builder.add_conditional_edges("critic", critic_router, {
        "deliver": "deliver",
        "revise": "brief_gen",       # Reflection Loop back to Generator with Feedback
        "end_pipeline": END
    })

    builder.add_edge("deliver", END)

    return builder.compile()


def run_multi_user_cron():
    print("=== Booting Agentic Daily Briefing Service ===")
    agent = build_platform_agent()
    db = SessionLocal()

    try:
        users = db.query(User).filter(User.is_active == True).all()
        if not users:
            print("🌱 No active users in database. Running with default mock user...")
            initial_state = {
                "user_id": "user_vyshakh_001",
                "user_preferences": ["technology", "ai", "business"],
                "retrieved_articles": [],
                "final_briefing": "",
                "critique_feedback": "",
                "retry_count": 0,
                "max_retries": 2,
                "briefing_approved": False,
            }
            result = agent.invoke(initial_state)
            if result.get("briefing_approved"):

                print("\n" + "=" * 50)

                print(
                    "📰 APPROVED DAILY BRIEFING OUTPUT:"
                )

                print("=" * 50)

                print(
                    result["final_briefing"]
                )

            else:

                print("\n" + "=" * 50)

                print(
                    "⚠️ BRIEFING NOT APPROVED"
                )

                print("=" * 50)

                print(
                    "The briefing failed quality review "
                    "and will not be delivered."
                )
            return

        for user in users:
            print(f"\n▶️ Starting pipeline for user: {user.name} ({user.id})")
            user_topics = [p.topic for p in user.preferences] or ["general"]
            
            initial_state = {
                "user_id": user.id,
                "user_preferences": user_topics,
                "retrieved_articles": [],
                "final_briefing": "",
                "critique_feedback": "",
                "retry_count": 0,
                "max_retries": 2,
                "briefing_approved": False,
            }
            
            result = agent.invoke(initial_state)

            print("\n" + "=" * 50)
            if result.get("briefing_approved"):
                print(f"📰 APPROVED DAILY BRIEFING — {user.name}:")
            else:
                print(f"📰 BEST-EFFORT BRIEFING — {user.name} (quality warning attached):")
            print("=" * 50)
            print(result.get("final_briefing", "No briefing generated."))
            print("=" * 50 + "\n")

    finally:
        db.close()


if __name__ == "__main__":
    run_multi_user_cron()