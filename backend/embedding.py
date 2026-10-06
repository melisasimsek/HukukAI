from sentence_transformers import SentenceTransformer

print("Model yükleniyor...")

model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

cumle = "Haksız yere işten çıkarıldım."

vektor = model.encode(cumle)

print("Vektör uzunluğu:", len(vektor))

print(vektor[:10])