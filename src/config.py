# src/config.py
import os
from dotenv import load_dotenv

# Automatically look for and load the .env file
load_dotenv()

class Config:
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Fail fast: Stop the program immediately if configurations are missing
    if not NEWS_API_KEY:
        raise ValueError("CRITICAL ERROR: NEWS_API_KEY is missing from your .env file.")
    if not DATABASE_URL:
        raise ValueError("CRITICAL ERROR: DATABASE_URL is missing from your .env file.")