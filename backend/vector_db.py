import chromadb

client = chromadb.PersistentClient(path="../models/chroma_db_yeni")

collection = client.get_or_create_collection(
    name="hukuk_kanunlari"
)

print("✅ ChromaDB hazır.")