import re
import logging
from typing import List, Dict, Any
from collections import Counter

logger = logging.getLogger(__name__)

class SpacyEntityExtractor:
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.nlp = None
        self.spacy_available = False
        self.model_name = model_name
        
        try:
            import spacy
            try:
                self.nlp = spacy.load(model_name)
                self.spacy_available = True
                logger.info(f"✅ spaCy loaded successfully with model: {model_name}")
            except OSError:
                logger.warning(f"⚠️ Model '{model_name}' not found.")
                try:
                    import subprocess
                    import sys
                    subprocess.run(
                        [sys.executable, "-m", "spacy", "download", model_name],
                        check=True,
                        capture_output=True
                    )
                    self.nlp = spacy.load(model_name)
                    self.spacy_available = True
                    logger.info(f"✅ spaCy model '{model_name}' downloaded and loaded")
                except Exception as e:
                    logger.warning(f"⚠️ Could not download spaCy model: {e}")
                    self.spacy_available = False
                    self._init_regex_patterns()
            except ImportError:
                logger.warning("⚠️ spaCy not installed")
                self.spacy_available = False
                self._init_regex_patterns()
        except Exception as e:
            logger.warning(f"⚠️ Error loading spaCy: {e}")
            self.spacy_available = False
            self._init_regex_patterns()
        
        self._init_regex_patterns()
        
        self.label_map = {
            'PERSON': 'PERSON', 'PER': 'PERSON',
            'ORG': 'ORGANIZATION', 'GPE': 'LOCATION',
            'LOC': 'LOCATION', 'DATE': 'DATE',
            'TIME': 'TIME', 'MONEY': 'MONEY',
            'PERCENT': 'PERCENT', 'FAC': 'FACILITY',
            'PRODUCT': 'PRODUCT', 'EVENT': 'EVENT',
            'LAW': 'LAW', 'NORP': 'NATIONALITY',
            'LANGUAGE': 'LANGUAGE', 'WORK_OF_ART': 'WORK_OF_ART',
        }
    
    def _init_regex_patterns(self):
        self.regex_patterns = {
            'PERSON': [
                r'\b(?:Mr\.|Ms\.|Mrs\.|Dr\.|Prof\.)\s+[A-Z][a-z]+\b',
                r'\b(?:Donald\s+Trump|Joe\s+Biden|Elon\s+Musk|Jeff\s+Bezos|Bill\s+Gates|Satya\s+Nadella|Sundar\s+Pichai|Tim\s+Cook|Mark\s+Zuckerberg|Sam\s+Altman|Kamala\s+Harris|JD\s+Vance|Rishi\s+Sunak|Narendra\s+Modi)\b'
            ],
            'ORGANIZATION': [
                r'\b(?:[A-Z][a-z]+\s+){1,3}(?:Inc\.|Corp\.|LLC|Co\.|Company|Corporation|Group|Holdings)\b',
                r'\b(?:Microsoft|Google|Apple|Amazon|OpenAI|Tesla|SpaceX|Meta|Netflix|Uber|Oracle|Salesforce|Adobe|Cisco|Intel|AMD|NVIDIA|IBM)\b'
            ],
            'LOCATION': [
                r'\b(?:New\s+York|Los\s+Angeles|Chicago|Houston|San\s+Francisco|Seattle|Denver|Washington|Boston|Miami|Atlanta|London|Paris|Tokyo|Singapore|Dubai|Shanghai|Beijing|Mumbai|Delhi|Bangalore)\b'
            ],
            'DATE': [
                r'\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b',
                r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b'
            ],
            'MONEY': [
                r'\$\s*\d+(?:,\d{3})*(?:\.\d{2})?',
                r'\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars|USD|EUR|GBP|JPY|INR)'
            ]
        }
    
    def extract(self, text: str) -> Dict[str, Any]:
        if not text or len(text.strip()) < 10:
            return {'entities': [], 'entity_counts': {}, 'method': 'none', 'total_entities': 0}
        
        if self.spacy_available:
            return self._extract_with_spacy(text)
        else:
            return self._extract_with_regex(text)
    
    def _extract_with_spacy(self, text: str) -> Dict[str, Any]:
        try:
            doc = self.nlp(text[:1000000])
            entities = []
            seen = set()
            entity_counts = Counter()
            
            for ent in doc.ents:
                entity_text = ent.text.strip()
                entity_label = ent.label_
                if len(entity_text) < 2:
                    continue
                mapped_label = self.label_map.get(entity_label, entity_label)
                key = f"{entity_text.lower()}_{mapped_label}"
                if key not in seen:
                    entities.append({
                        'text': entity_text,
                        'label': mapped_label,
                        'confidence': 1.0,
                        'start': ent.start_char,
                        'end': ent.end_char,
                        'entity_type': entity_label
                    })
                    seen.add(key)
                    entity_counts[mapped_label] += 1
            
            return {
                'entities': entities,
                'entity_counts': dict(entity_counts),
                'method': 'spacy',
                'total_entities': len(entities),
                'model': self.model_name
            }
        except Exception as e:
            logger.error(f"❌ spaCy extraction failed: {e}")
            return self._extract_with_regex(text)
    
    def _extract_with_regex(self, text: str) -> Dict[str, Any]:
        entities = []
        seen = set()
        entity_counts = Counter()
        
        for entity_type, patterns in self.regex_patterns.items():
            for pattern in patterns:
                try:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        entity_text = match.group()
                        if len(entity_text) < 2:
                            continue
                        key = f"{entity_text.lower()}_{entity_type}"
                        if key not in seen:
                            entities.append({
                                'text': entity_text,
                                'label': entity_type,
                                'confidence': 0.7,
                                'start': match.start(),
                                'end': match.end()
                            })
                            seen.add(key)
                            entity_counts[entity_type] += 1
                except Exception:
                    continue
        
        return {
            'entities': entities,
            'entity_counts': dict(entity_counts),
            'method': 'regex',
            'total_entities': len(entities)
        }
    
    def extract_from_article(self, title: str, description: str = "", content: str = "") -> Dict[str, Any]:
        combined_text = f"{title} {description} {content}".strip()
        if not combined_text:
            return {'entities': [], 'entity_counts': {}, 'method': 'none', 'total_entities': 0}
        result = self.extract(combined_text)
        result['title'] = title
        grouped = {}
        for entity in result.get('entities', []):
            label = entity.get('label', 'UNKNOWN')
            if label not in grouped:
                grouped[label] = []
            grouped[label].append(entity.get('text', ''))
        result['grouped_entities'] = grouped
        return result