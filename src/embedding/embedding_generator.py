# import logging
# from typing import List, Dict, Any, Optional
# from sentence_transformers import SentenceTransformer

# logger = logging.getLogger(__name__)

# class EmbeddingGenerator:
#     def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
#         self.model_name = model_name
#         self.model = None
#         self.embedding_dim = None
#         self.available = False
        
#         try:
#             self.model = SentenceTransformer(model_name)
#             self.embedding_dim = self.model.get_sentence_embedding_dimension()
#             self.available = True
#             logger.info(f"✅ Sentence Transformer loaded: {model_name}")
#             logger.info(f"   Embedding dimension: {self.embedding_dim}")
#         except Exception as e:
#             logger.error(f"❌ Failed to load Sentence Transformer: {e}")
#             self.available = False
    
#     def generate_embedding(self, text: str) -> Optional[List[float]]:
#         if not self.available or not text:
#             return None
#         try:
#             embedding = self.model.encode(text, normalize_embeddings=True)
#             return embedding.tolist()
#         except Exception as e:
#             logger.error(f"Embedding generation failed: {e}")
#             return None
    
#     def embed_article(self, title: str, description: str = "", content: str = "") -> Dict[str, Any]:
#         if not self.available:
#             return {'embedding': None, 'error': 'Embedding generator not available', 'dimension': 0}
        
#         text_parts = []
#         if title:
#             text_parts.append(f"Title: {title}")
#         if description:
#             text_parts.append(f"Description: {description}")
#         if content:
#             text_parts.append(f"Content: {content[:2000]}")
        
#         combined_text = " ".join(text_parts)
#         if not combined_text.strip():
#             return {'embedding': None, 'error': 'No text to embed', 'dimension': 0}
        
#         embedding = self.generate_embedding(combined_text)
#         return {
#             'embedding': embedding,
#             'dimension': self.embedding_dim if embedding else 0,
#             'model': self.model_name,
#             'text_length': len(combined_text)
#         }
    
#     def is_available(self) -> bool:
#         return self.available