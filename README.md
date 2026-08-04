# 📰 AI-Powered News Intelligence & Retrieval Platform

> An end-to-end AI-powered News Intelligence platform that automates multi-source news ingestion, semantic analysis, topic discovery, personalized recommendations, trust evaluation, contradiction detection, and Retrieval-Augmented Generation (RAG) for intelligent news exploration and executive briefings.

---

## 🚀 Overview

Modern news consumers face information overload, duplicate reporting, conflicting narratives, and difficulty identifying trustworthy information.

This project addresses these challenges by combining **Data Engineering, Natural Language Processing, Machine Learning, Vector Search, and Large Language Models** into a unified AI-powered News Intelligence platform.

The platform automatically:

- Collects news from multiple APIs and RSS feeds
- Cleans and enriches articles
- Removes duplicates
- Discovers semantic topics
- Generates vector embeddings
- Performs semantic retrieval
- Detects contradictory information
- Computes trust scores and recommendations
- Generates AI-powered executive briefings
- Answers natural language questions using Retrieval-Augmented Generation (RAG)
- Produces PDF reports and delivers personalized email briefings

---

# ✨ Features

## 📥 Multi-Source News Ingestion

- NewsAPI
- GNews
- Currents API
- New York Times API
- RSS Feeds
- Parallel data collection
- Circuit Breaker for resilient API communication

---

## 🧹 NLP Processing

- Text preprocessing
- Language detection
- Named Entity Recognition (spaCy)
- Metadata enrichment

---

## 📊 Topic Discovery

- BERTopic
- Semantic clustering
- Trend identification

---

## 🔍 Semantic Retrieval

- Sentence Transformers
- ChromaDB
- Vector similarity search
- Context-aware retrieval

---

## 🤖 Agentic AI

Built using **LangGraph** and **LangChain**.

### Executive Briefing Agent

- Retrieve latest news
- Rank recommendations
- Evaluate trust
- Detect contradictions
- Generate executive briefing

### Question Answering Agent

- Semantic Retrieval
- RAG
- Context Generation
- Critique
- Refinement
- Final grounded response

---

## 🛡 Trust & Reliability Layer

Unlike traditional RAG systems, this platform evaluates article reliability before generation.

Features include:

- Recommendation Engine
- Trust Scoring
- Source Credibility Analysis
- Freshness Scoring
- Natural Language Inference (NLI)-based Contradiction Detection

This enables the platform to identify conflicting reports across multiple publishers and generate more transparent, trustworthy AI responses.

---

## 📄 Automated Reporting

- Executive News Briefings
- AI-generated summaries
- PDF report generation
- Personalized email delivery

---

# 🏗 System Architecture

```
                             External News APIs / RSS
                               │
                               ▼
                    Parallel News Collection
                               │
                               ▼
                 Cleaning & NLP Preprocessing
                               │
                               ▼
                        Deduplication
                               │
                               ▼
                         PostgreSQL
                               │
          ┌────────────────────┴────────────────────┐
          │                                         │
          ▼                                         ▼
 Recommendation Engine                     BERTopic Clustering
          │                                         │
          ▼                                         ▼
 Trust Scoring                     Sentence Transformer Embeddings
          │                                         │
          ▼                                         ▼
 Platform Agent                              ChromaDB
          │                                         │
          ▼                                         ▼
 Executive Briefings                        Q&A Agent (RAG)
          │                                         │
          ▼                                         ▼
 PDF Generation                         Semantic Retrieval
          │                                         │
          ▼                                         ▼
 Personalised Emails                    LLM Response
```



---

# 🔄 End-to-End Workflow

```
News Sources
      │
      ▼
Parallel Ingestion
      │
      ▼
Preprocessing
      │
      ▼
Deduplication
      │
      ▼
BERTopic
      │
      ▼
Sentence Embeddings
      │
      ▼
ChromaDB
      │
      ▼
Recommendation Engine
      │
      ▼
Trust Scoring
      │
      ▼
Contradiction Detection
      │
      ▼
LangGraph Agents
      │
      ▼
Executive Briefings / RAG Q&A
      │
      ▼
PDF Reports + Email Delivery
```

---

# 🛠 Technology Stack

## Programming

- Python

## AI / GenAI

- LangChain
- LangGraph
- Prompt Engineering
- Retrieval-Augmented Generation (RAG)

## Machine Learning

- BERTopic
- Sentence Transformers

## NLP

- spaCy
- Named Entity Recognition
- Language Detection
- Natural Language Inference (NLI)

## Vector Database

- ChromaDB

## Database

- PostgreSQL
- SQLAlchemy

## Backend

- FastAPI

## Workflow Orchestration

- Prefect

## Frontend

- Streamlit

---

# 📂 Project Structure

```
src/
│
├── ingestion/
├── preprocessing/
├── enrichment/
├── deduplication/
├── semantic_representation/
├── topic_modeling/
├── contradiction/
├── recommendation/
├── generation/
├── vector_storage/
├── database/
│
├── platform_agent.py
├── qna_agent.py
├── rag_engine.py
└── main.py
```

---

# 🚀 Getting Started

## Clone the repository

```bash
git clone https://github.com/<your-username>/news-intelligence-platform.git

cd news-intelligence-platform
```

---

## Create a virtual environment

```bash
python -m venv venv

source venv/bin/activate
```

Windows

```bash
venv\Scripts\activate
```

---

## Install dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment Variables

Create a `.env` file.

Example:

```env
OPENAI_API_KEY=
NEWS_API_KEY=
GNEWS_API_KEY=
CURRENTS_API_KEY=
NYTIMES_API_KEY=

DATABASE_URL=

CHROMA_PATH=
```

---

## Run the application

```bash
python main.py
```

---

---

## Run Prefect Orchestration

Start the Prefect server:

```bash
prefect server start
```

Configure the Prefect API (run once):

```bash
prefect config set PREFECT_API_URL=http://127.0.0.1:4200/api
```

Start the scheduled workflows:

```bash
python -m Orchestration.prefect_flows
```

Open the Prefect Dashboard:

```
http://127.0.0.1:4200
```

The following workflows will be scheduled automatically:

- **News Ingestion Pipeline** – Every 3 hours
- **Daily News Briefing Pipeline** – Every day at 7:00 AM (Asia/Kolkata)

---

---


### Contradiction Detection Demo

To populate the database with demo contradiction data, run:

```bash
python -m scripts.seed_demo_contradictions
```

This script:

- Inserts fictional contradictory news articles into the `raw_articles` table.
- Executes the project's DeBERTa-based contradiction detection pipeline.
- Automatically stores detected contradiction pairs in the `article_contradictions` table.
- Can be run multiple times without creating duplicate demo records.

The script is intended only for demonstration and testing purposes and does not affect the normal news ingestion pipeline.

---


# 🎯 Future Enhancements

- Hybrid Retrieval (BM25 + Vector Search)
- Cross-Encoder Re-ranking
- Redis Caching
- Docker Deployment
- Kubernetes
- Kafka Streaming
- Multi-Agent Collaboration
- Knowledge Graph Integration
- User Feedback Learning
- Real-time News Streaming

---



# ⭐ If you found this project useful, consider giving it a star!
