import sys
import os
from typing import TypedDict, List, Dict, Any, Literal
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

# Load environment variables and project root
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import SessionLocal, engine, Base
from src.database.models import RawArticles,DailyBriefing


# Ensure tables are created when the agent boots
Base.metadata.create_all(bind=engine)

# --- 1. Define the Shared Memory (State) ---
class PlatformState(TypedDict):
    user_id: str
    user_preferences: List[str]   # e.g., ["technology", "ai"]
    retrieved_articles: List[Dict]
    evaluator_status: str         # "approved" or "retry"
    retry_count: int
    final_briefing: str

# --- 2. Define the Agent Nodes ---

def data_retrieval_node(state: PlatformState):
    """Pulls articles from PostgreSQL filtered by the user's preferred topics."""
    print(f"📥 RETRIEVAL: Fetching articles for preferences: {state['user_preferences']}...")
    db = SessionLocal()
    
    try:
        # Query Postgres for articles matching user preferred topics
        # (Using primary_topic or fallback to general if empty)
        articles = (
            db.query(RawArticles)
            .filter(RawArticles.primary_topic.in_(state["user_preferences"]))
            .order_by(RawArticles.published_at.desc())
            .limit(5)
            .all()
        )
        
        # If no articles match specific preferences, fetch the latest general articles
        if not articles:
            print("   ⚠️ No direct matches found. Fetching latest general articles...")
            articles = db.query(RawArticles).order_by(RawArticles.published_at.desc()).limit(5).all()
            
        formatted_articles = []
        for art in articles:
            formatted_articles.append({
                "title": art.title,
                "content": art.cleaned_content or art.description or "",
                "source": art.source_name,
                "topic": art.primary_topic
            })
            
        print(f"   -> Successfully retrieved {len(formatted_articles)} articles from PostgreSQL.")
        return {"retrieved_articles": formatted_articles}
        
    except Exception as e:
        print(f"❌ Database Retrieval Error: {e}")
        return {"retrieved_articles": []}
    finally:
        db.close()


def evaluator_node(state: PlatformState) -> Literal["brief_gen", "end_pipeline"]:
    """Evaluates if we have enough context to generate a briefing."""
    print("🧐 EVALUATOR: Inspecting retrieved dataset quality...")
    articles = state.get("retrieved_articles", [])
    retry_count = state.get("retry_count", 0)
    
    if len(articles) < 2 and retry_count < 1:
        print("   -> Insufficient articles found. Triggering fallback retrieval loop.")
        return "end_pipeline" # Or route back if fallback is configured
        
    print("   -> Dataset verified. Proceeding to Brief Generation.")
    return "brief_gen"


def brief_gen_node(state: PlatformState):
    """Synthesizes the daily briefing using Groq (Llama 3.3)."""
    print("✍️  BRIEF GEN: Synthesizing personalized daily briefing via Groq...")
    
    articles = state.get("retrieved_articles", [])
    context = "\n\n".join([f"Title: {a['title']}\nSource: {a['source']}\nContent: {a['content']}" for a in articles])
    
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
    
    prompt = f"""You are an expert personalized news editor. Generate a concise, engaging daily briefing for a user interested in: {', '.join(state['user_preferences'])}.
    
    Base your briefing ONLY on the following source articles retrieved from the database today:
    {context}
    
    Structure the briefing cleanly with key highlights, trends, and source mentions. Do not hallucinate.
    """
    
    response = llm.invoke(prompt)
    print("   -> Briefing generated successfully.")
    return {"final_briefing": response.content}


def delivery_node(state: PlatformState):
    """Saves the daily briefing to the PostgreSQL DailyBriefings table."""
    print("🚀 DELIVERY: Finalizing briefing delivery (Saving to DailyBriefings table)...")
    
    db = SessionLocal()
    try:
        new_briefing = DailyBriefing(
            user_id=state.get("user_id", "unknown_user"),
            topic_preferences=",".join(state.get("user_preferences", [])),
            content=state.get("final_briefing", "")
        )
        db.add(new_briefing)
        db.commit()
        print("   -> Briefing successfully saved to PostgreSQL.")
    except Exception as e:
        db.rollback()
        print(f"❌ Database Insertion Error: {e}")
    finally:
        db.close()
        
    return state


# --- 3. Wire the LangGraph Platform Agent ---
def build_platform_agent():
    builder = StateGraph(PlatformState)

    # Register nodes
    builder.add_node("retrieve", data_retrieval_node)
    builder.add_node("brief_gen", brief_gen_node)
    builder.add_node("deliver", delivery_node)

    # Establish edges
    builder.add_edge(START, "retrieve")
    builder.add_conditional_edges("retrieve", evaluator_node, {
        "brief_gen": "brief_gen",
        "end_pipeline": END
    })
    builder.add_edge("brief_gen", "deliver")
    builder.add_edge("deliver", END)

    return builder.compile()


if __name__ == "__main__":
    print("=== Booting Platform Agent (Daily Briefing Service) ===")
    agent = build_platform_agent()
    
    # Mocking a user profile for testing
    initial_state = {
        "user_id": "user_vyshakh_001",
        "user_preferences": ["technology", "ai", "business"],
        "retry_count": 0,
        "retrieved_articles": [],
        "final_briefing": ""
    }
    
    # Run the agent workflow
    result = agent.invoke(initial_state)
    
    if result.get("final_briefing"):
        print("\n" + "="*50)
        print("📰 PERSONALIZED DAILY BRIEFING OUTPUT:")
        print("="*50)
        print(result["final_briefing"])
    else:
        print("\n⚠️ Pipeline ended without generating a briefing due to low article counts.")