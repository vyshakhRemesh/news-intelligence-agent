# src/config.py
import os
from dotenv import load_dotenv

# Automatically look for and load the .env file
load_dotenv()

class Config:
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")
    GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
    CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:447424@localhost:5432/news_intelligence")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 5432))
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "447424")
    DB_NAME = os.getenv("DB_NAME", "news_intelligence")
    
    # ============================================
    # CHROMADB
    # ============================================
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "news_articles")
    
    # ============================================
    # EMBEDDING
    # ============================================
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    
    # ============================================
    # SPACY
    # ============================================
    SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")
    
    # ============================================
    # LOGGING
    # ============================================
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Fail fast: Stop the program immediately if configurations are missing
    if not NEWS_API_KEY:
        raise ValueError("CRITICAL ERROR: NEWS_API_KEY is missing from your .env file.")
    if not DATABASE_URL:
        raise ValueError("CRITICAL ERROR: DATABASE_URL is missing from your .env file.")