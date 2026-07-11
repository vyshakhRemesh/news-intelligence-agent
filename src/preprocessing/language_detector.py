import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class LanguageDetector:
    def detect(self, text: str) -> Dict[str, Any]:
        if not text or len(text.strip()) < 10:
            return {'language': 'unknown', 'confidence': 0.0}
        
        text_lower = text.lower()
        
        # Check for Hindi
        hindi_chars = sum(1 for c in text if 0x0900 <= ord(c) <= 0x097F)
        total_chars = len(re.sub(r'\s', '', text))
        if total_chars > 0 and (hindi_chars / total_chars) > 0.15:
            return {'language': 'hi', 'confidence': 0.7}
        
        # English common words
        en_words = {'the', 'and', 'to', 'of', 'for', 'with', 'on', 'at', 'from', 'by',
                   'in', 'that', 'this', 'are', 'was', 'were', 'have', 'has', 'had',
                   'will', 'would', 'could', 'should', 'may', 'might', 'must'}
        words = set(text_lower.split())
        en_matches = len(words.intersection(en_words))
        
        if en_matches > 2:
            confidence = min(en_matches / 10, 1.0)
            return {'language': 'en', 'confidence': confidence}
        
        return {'language': 'unknown', 'confidence': 0.0}