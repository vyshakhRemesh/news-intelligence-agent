import chromadb

client = chromadb.PersistentClient(path="./chroma_db")

collection = client.get_collection("news_articles")

print("=" * 50)
print("ChromaDB Verification")
print("=" * 50)

print("Collection Name :", collection.name)
print("Total Articles  :", collection.count())

sample = collection.peek(limit=3)

print("\nSample IDs:")
print(sample["ids"])

print("\nSample Metadata:")
for metadata in sample["metadatas"]:
    print(metadata)

print("\nSample Documents:")
for doc in sample["documents"]:
    print(doc[:100])
    print("-" * 50)