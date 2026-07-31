from typing import TypedDict

from src.semantic_representation.embedding_generator import EmbeddingGenerator
from src.vector_storage.chroma_manager import ChromaManager

from src.generation.rag_engine import NewsGenerationEngine
import json

from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

from src.database.connection import SessionLocal


# ==========================================================
# State
# ==========================================================

class QnAState(TypedDict):

    question: str

    retrieved_articles: list

    generated_answer: str

    critique_feedback: str

    # critique_decision: str

    revision_count: int


# ==========================================================
# Components
# ==========================================================

embedding_generator = EmbeddingGenerator()

chroma_manager = ChromaManager()



# ==========================================================
# Retrieval Node
# ==========================================================

def retrieve_node(state: QnAState):

    question = state["question"]

    print("\n==============================")
    print("RETRIEVAL NODE")
    print("==============================")

    print(f"Question: {question}")

    results = chroma_manager.search_by_text(
        query_text=question,
        top_k=5,
        embedder=embedding_generator,
    )

    retrieved_articles = []

    ids = results.get("ids", [])

    if not ids:
        print("No articles found.")
        return {"retrieved_articles": []}

    ids = ids[0]
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for article_id, document, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
    ):

        article = {
            "article_id": article_id,
            "content": document,
            "distance": distance,
            **(metadata or {}),
        }

        retrieved_articles.append(article)

    print(f"Retrieved {len(retrieved_articles)} articles.")

    for i, article in enumerate(retrieved_articles, 1):

        print(
            f"{i}. {article.get('title','No title')}"
        )

    return {
        "retrieved_articles": retrieved_articles,
    }


# ==========================================================
# LangGraph
# ==========================================================

builder = StateGraph(QnAState)

builder.add_node(
    "retrieve",
    retrieve_node,
)


# ==========================================================
# Initial State (Dummy Question)
# ==========================================================

initial_state = {

    "question": "What are the latest developments in artificial intelligence?",

    "retrieved_articles": [],

    "generated_answer": "",

    "critique_feedback": "",

    # "critique_decision": "",

    "revision_count": 0,
}


def generate_node(state: QnAState):

    print("\n==============================")
    print("GENERATOR NODE")
    print("==============================")

    print(f"Revision {state.get('revision_count',0)}")


    if not state["retrieved_articles"]:

        return {
            "generated_answer": "I couldn't find any relevant news articles to answer your question."
        }

    db = SessionLocal()

    try:

        generation_engine = NewsGenerationEngine(db=db)

        answer = generation_engine.generate_briefing(

            question=state["question"],

            retrieved_articles=state["retrieved_articles"],

            critique_feedback=state.get(
                "critique_feedback",
                "",
            ),

        )

        return {
            "generated_answer": answer
        }

    except Exception as e:

        print(f"Generator Error: {e}")

        return {
            "generated_answer": ""
        }

    finally:

        db.close()


def critic_node(state: QnAState):

    print("\n==============================")
    print("CRITIC NODE")
    print("==============================")

    answer = state.get(
        "generated_answer",
        "",
    )

    articles = state.get(
        "retrieved_articles",
        [],
    )

    revision_count = state.get(
        "revision_count",
        0,
    )

    if not answer:

        return {

            "critique_feedback":
                "Generated answer was empty.",

            "revision_count":
                revision_count + 1,
        }

    llm = ChatGroq(
        model_name="llama-3.3-70b-versatile",
        temperature=0,
    )

    prompt = f"""
You are a strict quality reviewer.

Question:
{state["question"]}

Retrieved Articles:
{len(articles)}

Generated Answer:
{answer}

Evaluate:

1. Did it answer the question?

2. Did it stay within the supplied context?

3. Is it factual and coherent?

Return ONLY JSON.

{{
    "status":"APPROVED" or "NEEDS_REVISION",
    "feedback":"reason"
}}
"""

    try:

        response = llm.invoke(prompt)

        content = response.content.strip()

        if content.startswith("```json"):
            content = content[7:-3].strip()

        elif content.startswith("```"):
            content = content[3:-3].strip()

        review = json.loads(content)

        status = review.get(
            "status",
            "APPROVED",
        )

        feedback = review.get(
            "feedback",
            "",
        )

        print(status)

    

        if status == "APPROVED":

            return {

                "critique_feedback": "",

                "revision_count":
                    revision_count,
            }

        return {

            "critique_feedback":
                feedback,

            "revision_count":
                revision_count + 1,
        }

    except Exception as e:

        print(e)

        return {

            "critique_feedback": "",

            "revision_count":
                revision_count,
        }


def critic_router(state: QnAState):

    MAX_REVISIONS = 2

    if state["revision_count"] >= MAX_REVISIONS:

        return "finish"

    if state["critique_feedback"]:

        return "revise"

    return "finish"


builder.add_node(
    "generate",
    generate_node,
)

builder.add_node(
    "critic",
    critic_node,
)

builder.add_edge(
    START,
    "retrieve",
)

builder.add_edge(
    "retrieve",
    "generate",
)

builder.add_edge(
    "generate",
    "critic",
)

builder.add_conditional_edges(
    "critic",
    critic_router,
    {
        "revise": "generate",
        "finish": END,
    },
)

qna_agent = builder.compile()

# def run_qna():

#     result = qna_agent.invoke(initial_state)

#     print("\n")
#     print("=" * 80)
#     print("FINAL ANSWER")
#     print("=" * 80)

#     print(result["generated_answer"])


def run_qna():

    while True:

        question = input("\nAsk a question (or 'exit'): ")

        if question.lower() == "exit":
            break

        initial_state = {
            "question": question,
            "retrieved_articles": [],
            "generated_answer": "",
            "critique_feedback": "",
            "revision_count": 0,
        }

        result = qna_agent.invoke(initial_state)

        print("\n" + "=" * 80)
        print(result["generated_answer"])

if __name__ == "__main__":

    run_qna()