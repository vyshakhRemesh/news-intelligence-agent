import re
import unicodedata
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TextCleaner:
    def clean(self, text: str) -> Dict[str, Any]:
        if not text or not isinstance(text, str):
            return self._empty_result()
        
        text = re.sub(r'<[^>]+>', ' ', text)
        try:
            text = unicodedata.normalize('NFKD', text)
            text = text.encode('ascii', 'ignore').decode('utf-8')
        except:
            pass
        
        text = re.sub(r'[^a-zA-Z0-9\s.,!?-]', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        clean_for_count = re.sub(r'[^\w\s]', '', text)
        words = clean_for_count.split()
        
        return {
            'cleaned_text': text,
            'word_count': len(words),
            'character_count': len(text.replace(' ', '')),
            'sentence_count': len(re.findall(r'[.!?]+', text)),
            'avg_word_length': sum(len(w) for w in words) / len(words) if words else 0,
            'has_content': len(text.strip()) > 0
        }
    
    def _empty_result(self) -> Dict[str, Any]:
        return {
            'cleaned_text': '',
            'word_count': 0,
            'character_count': 0,
            'sentence_count': 0,
            'avg_word_length': 0,
            'has_content': False
        }