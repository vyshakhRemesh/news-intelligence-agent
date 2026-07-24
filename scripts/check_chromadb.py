import os
import sys

print("Python:", sys.executable)
print("Working Directory:", os.getcwd())
print("sys.path:")
for p in sys.path:
    print(" ", p)






import chromadb
from src.config import Config
client = chromadb.PersistentClient(path=Config.CHROMA_DB_PATH)

print("=" * 50)

collections = client.list_collections()

print("Collections:")

for c in collections:
    print(f"- {c.name}")

print("=" * 50)

collection = client.get_collection(Config.CHROMA_COLLECTION)

print("Total Documents :", collection.count())

sample = collection.peek(limit=5)

print("\nSample IDs:")
print(sample["ids"])

print("\nSample Metadata:")
print(sample["metadatas"])

print("=" * 50)