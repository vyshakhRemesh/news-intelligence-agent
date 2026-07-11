import re
import logging
from typing import Dict, Any, List
from datetime import datetime

try:
    from textblob import TextBlob
    TEXTBLOB_AVAILABLE = True
except ImportError:
    TEXTBLOB_AVAILABLE = False

logger = logging.getLogger(__name__)

class DataEnricher:
    def __init__(self):
        self.textblob_available = TEXTBLOB_AVAILABLE
        self.topic_keywords = {
            'technology': ['ai', 'machine learning', 'software', 'hardware', 'cloud', 'digital', 'tech'],
            'business': ['market', 'stock', 'investment', 'finance', 'economic', 'trade', 'profit'],
            'politics': ['government', 'election', 'vote', 'parliament', 'president', 'policy'],
            'health': ['healthcare', 'medical', 'hospital', 'disease', 'vaccine', 'treatment'],
            'science': ['research', 'scientist', 'discovery', 'experiment', 'space', 'climate'],
            'sports': ['football', 'cricket', 'basketball', 'tennis', 'olympic', 'match'],
            'entertainment': ['movie', 'music', 'concert', 'streaming', 'celebrity', 'award'],
            'crime': ['crime', 'police', 'murder', 'theft', 'investigation', 'court']
        }
        logger.info("✅ Data Enricher initialized")
    
    def enrich_article(self, title: str, description: str = "", content: str = "") -> Dict[str, Any]:
        combined_text = f"{title} {description} {content}".strip()
        if not combined_text:
            return {'error': 'No text provided for enrichment'}
        
        enrichment = {
            'title': title,
            'description': description,
            'content': content,
            'enriched_at': datetime.utcnow().isoformat()
        }
        
        sentiment = self._analyze_sentiment(combined_text)
        enrichment['sentiment'] = sentiment
        
        topics = self._classify_topics(combined_text)
        enrichment['topics'] = topics
        enrichment['primary_topic'] = topics[0] if topics else 'general'
        
        keyphrases = self._extract_keyphrases(combined_text)
        enrichment['keyphrases'] = keyphrases[:10]
        
        readability = self._calculate_readability(combined_text)
        enrichment['readability'] = readability
        
        stats = self._get_text_statistics(combined_text)
        enrichment['statistics'] = stats
        
        quality_score = self._calculate_quality_score(enrichment)
        enrichment['quality_score'] = quality_score
        
        complexity = self._analyze_language_complexity(combined_text)
        enrichment['language_complexity'] = complexity
        
        enrichment['enrichment_summary'] = self.get_enrichment_summary(enrichment)
        
        return enrichment
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        if not self.textblob_available or not text:
            return {'polarity': 0, 'subjectivity': 0, 'label': 'neutral'}
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            if polarity > 0.3:
                label = 'positive'
            elif polarity < -0.3:
                label = 'negative'
            else:
                label = 'neutral'
            return {'polarity': round(polarity, 3), 'subjectivity': round(subjectivity, 3), 'label': label}
        except:
            return {'polarity': 0, 'subjectivity': 0, 'label': 'unknown'}
    
    def _classify_topics(self, text: str) -> List[str]:
        text_lower = text.lower()
        topic_scores = {}
        for topic, keywords in self.topic_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > 0:
                topic_scores[topic] = score
        sorted_topics = sorted(topic_scores.items(), key=lambda x: x[1], reverse=True)
        return [topic for topic, score in sorted_topics if score > 0][:5] or ['general']
    
    def _extract_keyphrases(self, text: str) -> List[str]:
        if not text:
            return []
        keyphrases = []
        capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b', text)
        for phrase in capitalized:
            if len(phrase.split()) >= 2 and phrase not in keyphrases:
                keyphrases.append(phrase)
        company_pattern = r'\b[A-Z][a-z]+\s+(?:Inc\.|Corp\.|LLC|Co\.|Company)\b'
        companies = re.findall(company_pattern, text)
        for company in companies:
            if company not in keyphrases:
                keyphrases.append(company)
        return keyphrases[:10]
    
    def _calculate_readability(self, text: str) -> Dict[str, Any]:
        if not text or len(text) < 50:
            return {'score': 0, 'level': 'unknown', 'avg_sentence_length': 0}
        try:
            clean_text = re.sub(r'[^a-zA-Z\s\.!?]', '', text)
            sentences = [s.strip() for s in re.split(r'[.!?]+', clean_text) if s.strip()]
            words = clean_text.split()
            if not sentences or not words:
                return {'score': 0, 'level': 'unknown', 'avg_sentence_length': 0}
            num_sentences = len(sentences)
            num_words = len(words)
            num_syllables = sum(self._count_syllables(word) for word in words)
            avg_sentence_length = num_words / num_sentences if num_sentences > 0 else 0
            avg_syllables_per_word = num_syllables / num_words if num_words > 0 else 0
            flesch_score = 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
            flesch_score = max(0, min(100, flesch_score))
            if flesch_score >= 80:
                level = 'easy'
            elif flesch_score >= 60:
                level = 'moderate'
            elif flesch_score >= 40:
                level = 'difficult'
            else:
                level = 'very_difficult'
            return {
                'score': round(flesch_score, 1),
                'level': level,
                'avg_sentence_length': round(avg_sentence_length, 1),
                'num_sentences': num_sentences,
                'num_words': num_words
            }
        except:
            return {'score': 0, 'level': 'unknown', 'avg_sentence_length': 0}
    
    def _count_syllables(self, word: str) -> int:
        word = word.lower()
        count = 0
        vowels = 'aeiouy'
        if not word:
            return 0
        if word[0] in vowels:
            count += 1
        for i in range(1, len(word)):
            if word[i] in vowels and word[i-1] not in vowels:
                count += 1
        if word.endswith('e'):
            count -= 1
        if word.endswith('le') and len(word) > 2:
            count += 1
        return max(1, count)
    
    def _get_text_statistics(self, text: str) -> Dict[str, Any]:
        if not text:
            return {'word_count': 0, 'character_count': 0, 'sentence_count': 0}
        clean_text = re.sub(r'[^a-zA-Z\s]', '', text)
        words = clean_text.split()
        sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
        return {
            'word_count': len(words),
            'character_count': len(text.replace(' ', '')),
            'sentence_count': len(sentences)
        }
    
    def _calculate_quality_score(self, enrichment: Dict[str, Any]) -> int:
        score = 0
        word_count = enrichment.get('statistics', {}).get('word_count', 0)
        if word_count > 500:
            score += 30
        elif word_count > 300:
            score += 25
        elif word_count > 150:
            score += 15
        elif word_count > 50:
            score += 5
        
        readability = enrichment.get('readability', {})
        flesch_score = readability.get('score', 0)
        if flesch_score >= 60:
            score += 20
        elif flesch_score >= 40:
            score += 10
        
        sentiment = enrichment.get('sentiment', {})
        if sentiment.get('label') in ['positive', 'negative']:
            score += 10
        
        keyphrases = enrichment.get('keyphrases', [])
        if len(keyphrases) >= 5:
            score += 15
        elif len(keyphrases) >= 3:
            score += 10
        
        topics = enrichment.get('topics', [])
        if len(topics) >= 3:
            score += 15
        elif len(topics) >= 2:
            score += 10
        
        return min(100, score)
    
    def _analyze_language_complexity(self, text: str) -> Dict[str, Any]:
        if not text or len(text) < 50:
            return {'vocabulary_richness': 0, 'complexity_level': 'low'}
        try:
            clean_text = re.sub(r'[^a-zA-Z\s]', '', text)
            words = clean_text.lower().split()
            if not words:
                return {'vocabulary_richness': 0, 'complexity_level': 'low'}
            unique_words = len(set(words))
            total_words = len(words)
            vocabulary_richness = unique_words / total_words if total_words > 0 else 0
            if vocabulary_richness > 0.6:
                complexity_level = 'high'
            elif vocabulary_richness > 0.4:
                complexity_level = 'medium'
            else:
                complexity_level = 'low'
            return {'vocabulary_richness': round(vocabulary_richness, 3), 'complexity_level': complexity_level}
        except:
            return {'vocabulary_richness': 0, 'complexity_level': 'low'}
    
    def get_enrichment_summary(self, enrichment: Dict[str, Any]) -> str:
        if not enrichment or 'error' in enrichment:
            return "No enrichment data available"
        parts = []
        sentiment = enrichment.get('sentiment', {})
        parts.append(f"Sentiment: {sentiment.get('label', 'unknown')}")
        parts.append(f"Topic: {enrichment.get('primary_topic', 'general')}")
        readability = enrichment.get('readability', {})
        parts.append(f"Readability: {readability.get('level', 'unknown')}")
        parts.append(f"Quality: {enrichment.get('quality_score', 0)}/100")
        keyphrases = enrichment.get('keyphrases', [])[:3]
        if keyphrases:
            parts.append(f"Keyphrases: {', '.join(keyphrases)}")
        return " | ".join(parts)