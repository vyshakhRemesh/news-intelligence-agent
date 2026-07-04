from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

class EmbeddingGenerator:

    def __init__(self):
        logger.info("Loading MiniLM model...")
        self.model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    def generate_embedding(self, text):

        if not text:
            return None

        embedding = self.model.encode(
            text,
            convert_to_numpy=True
        )

        return embedding.tolist()
    

# if __name__ == "__main__":

#     generator = EmbeddingGenerator()

#     text = """
#     Google launches Gemini AI update.
#     The company announced several new AI features.
#     """

#     embedding = generator.generate_embedding(text)

#     print("Embedding generated successfully!")
#     print("Dimensions:", len(embedding))
#     print("First 10 values:", embedding[:10])