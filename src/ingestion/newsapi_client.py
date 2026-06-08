# src/ingestion/newsapi_client.py
import requests
import logging
from typing import List, Dict, Optional
from src.config import Config

# Set up logging for this specific module
logger = logging.getLogger(__name__)

class NewsAPIClient:
    """
    A robust client for fetching live news articles from NewsAPI.
    """
    # The base URL for the API
    BASE_URL = "https://newsapi.org/v2"

    def __init__(self):
        # We grab the secure API key from our config file
        self.api_key = Config.NEWS_API_KEY
        
        # NewsAPI requires the key to be sent in the 'Headers' of the request, 
        # not in the visible URL, for security reasons.
        self.headers = {
            "X-Api-Key": self.api_key
        }

    def fetch_top_headlines(self, category: str = "general", language: str = "en", page_size: int = 100) -> Optional[List[Dict]]:
        """
        Connects to the top-headlines endpoint and returns a list of article dictionaries.
        """
        endpoint = f"{self.BASE_URL}/top-headlines"
        
        # These are the filters we apply to the search
        params = {
            "category": category,
            "language": language,
            "pageSize": page_size
        }

        try:
            logger.info(f"Connecting to NewsAPI to fetch top '{category}' headlines...")
            
            # The actual HTTP GET request. We enforce a 10-second timeout so our 
            # pipeline doesn't freeze forever if the API server crashes.
            response = requests.get(endpoint, headers=self.headers, params=params, timeout=10)
            
            # If the API returns an error code (like 401 Unauthorized or 404 Not Found),
            # this line instantly raises an exception so we know about it.
            response.raise_for_status() 
            
            # Convert the raw JSON text from the internet into a Python Dictionary
            data = response.json()
            
            if data.get("status") == "ok":
                articles = data.get("articles", [])
                logger.info(f"Success! Fetched {len(articles)} articles from NewsAPI.")
                return articles
            else:
                logger.error(f"NewsAPI returned a logical error: {data.get('message')}")
                return None

        except requests.exceptions.RequestException as e:
            # This catches internet connection drops or timeout failures
            logger.error(f"Network error while fetching from NewsAPI: {e}")
            return None