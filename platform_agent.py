import sys
import os
import json
from typing import TypedDict, List, Dict, Any, Literal
from dotenv import load_dotenv
from sqlalchemy import func
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

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
    user_preferences: List[str]     # e.g., ["technology", "ai"]
    retrieved_articles: List[Dict]
    final_briefing: str
    critique_feedback: str          # Stores feedback from the Critic Node
    retry_count: int                # Tracks revision/retrieval attempts
    max_retries: int                # Hard cap to prevent infinite loops


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

        # taking extra articles insted of 5 so that we can avoid duplicates and same source news

        selected_articles = []
        seen_article_ids = set()
        source_counts = {}

        for article, recommendation in articles:

            # Defense against duplicate join results
            if article.id in seen_article_ids:
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

        for i, article in enumerate(formatted_articles, 1):
            print(
                f"   {i}. {article['title']}\n"
                f"      Topic: {article['topic']}\n"
                f"      Source: {article['source']}\n"
                f"      Recommendation: {article.get('recommendation_score')}\n"
                f"      Trust: {article.get('trust_score')}\n"
                f"      Freshness: {article.get('freshness_score')}\n"
            )
        return {"retrieved_articles": formatted_articles}
        
    except Exception as e:
        print(f"❌ Retrieval Error: {e}")
        return {"retrieved_articles": []}
    finally:
        db.close()


def retry_retrieval_node(state: PlatformState):
    """Fallback: Broadens search by pulling general articles if topic filters yielded too few."""
    print("🔁 RETRY RETRIEVAL: Broadening search — dropping topic constraints...")
    db = SessionLocal()
    try:
        # articles = (
        #     db.query(RawArticles)
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

        selected_articles = []
        seen_article_ids = set()
        source_counts = {}

        for article, recommendation in articles:

            # Defense against duplicate join results
            if article.id in seen_article_ids:
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
        #         "topic": art.primary_topic,
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

                # Recommendation fields
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

                "source_preference_score": (
                    recommendation.source_preference_score
                    if recommendation else None
                ),
            }
            for article, recommendation in selected_articles
        ]

        print(f"   -> Broadened retrieval returned {len(formatted_articles)} articles.")
        return {
            "retrieved_articles": formatted_articles,
            "retry_count": state.get("retry_count", 0) + 1,
        }

    except Exception as e:
        print(f"❌ Retry Retrieval Error: {e}")
        return {
            "retrieved_articles": [],
            "retry_count": state.get("retry_count", 0) + 1
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
                "Generate a personalized daily news briefing covering the "
                "top distinct news stories for the user's preferences: "
                f"{', '.join(preferences)}. "
                "Cover each important retrieved story separately. "
                "Do not repeatedly discuss the same event. "
                "Do not force unrelated stories into a single narrative."
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
        return {"critique_feedback": "Draft was empty.", "retry_count": retry_count + 1}

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
            return {"critique_feedback": "", "retry_count": retry_count}
        else:
            return {
                "critique_feedback": feedback, 
                "retry_count": retry_count + 1
            }

    except Exception as e:
        print(f"⚠️ Critic evaluation error ({e}). Defaulting to APPROVED.")
        return {"critique_feedback": "", "retry_count": retry_count}


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
        print(
            f"   -> Max retries ({max_retries}) reached "
            "without critic approval. Terminating pipeline."
        )
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
                "max_retries": 2
            }
            result = agent.invoke(initial_state)
            if result.get("final_briefing"):
                print("\n" + "="*50)
                print("📰 APPROVED DAILY BRIEFING OUTPUT:")
                print("="*50)
                print(result["final_briefing"])
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
                "max_retries": 2
            }
            
            agent.invoke(initial_state)

    finally:
        db.close()


if __name__ == "__main__":
    run_multi_user_cron()