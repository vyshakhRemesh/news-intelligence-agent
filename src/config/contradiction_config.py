"""
Configuration for contradiction detection.
"""

# Number of similar articles to retrieve from ChromaDB
TOP_K_SIMILAR = 5

# Minimum cosine similarity required
SIMILARITY_THRESHOLD = 0.75

# NLI probability threshold for contradiction
CONTRADICTION_THRESHOLD = 0.70

# Maximum contradictory articles to display
MAX_CONTRADICTIONS = 5