# src/config.py
import os
from dotenv import load_dotenv

# Automatically look for and load the .env file
load_dotenv()

class Config:

    DATABASE_URL = os.getenv("DATABASE_URL")

    NEWS_API_KEY = os.getenv("NEWS_API_KEY")
    GNEWS_API_KEY = os.getenv("GNEWS_API_KEY")
    MEDIASTACK_API_KEY = os.getenv("MEDIASTACK_API_KEY")
    CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY")
    NYTIMES_API_KEY = os.getenv("NYTIMES_API_KEY")

    if not DATABASE_URL:
        raise ValueError(
            "DATABASE_URL missing from .env"
        )