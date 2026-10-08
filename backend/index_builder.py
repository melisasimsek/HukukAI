import json
import re
import shutil
import os

import chromadb
from sentence_transformers import SentenceTransformer


print("Program başladı.")

print("Embedding modeli yükleniyor...")
model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)
print("Embedding modeli hazır.")


# ESKİ CHROMADB'Yİ TEMİZLE
db_path = "../models/chroma_db_yeni"

if os.path.exists(db_path):
    shutil.rmtree(db_path)
    print("Eski ChromaDB silindi.")


client = chromadb.PersistentClient(
    path=db_path
)

collection = client.get_or_create_collection(
    name="hukuk_kanunlari"
)


with open(
    "../dataset/hukuk_dataset.json",
    "r",
    encoding="utf-8"
) as f:
    dataset = json.load(f)


print("Toplam kayıt:", len(dataset))


def kanun_no_bul(kanun):
    eslesme = re.match(
        r"\s*(\d+)",
        str(kanun)
    )

    if eslesme:
        return eslesme.group(1)

    return ""


batch_size = 100


for baslangic in range(
    0,
    len(dataset),
    batch_size
):

    batch = dataset[
        baslangic:baslangic + batch_size
    ]

    documents = [
        kayit["icerik"]
        for kayit in batch
    ]

    ids = [
        str(baslangic + i)
        for i in range(len(batch))
    ]

    metadatas = []

    for kayit in batch:

        madde = str(
            kayit.get(
                "madde_no",
                ""
            )
        )

        madde_turu = str(
    kayit.get("madde_turu") or "NORMAL MADDE"
)

        kanun = str(
            kayit.get(
                "kanun",
                ""
            )
        )

        metadatas.append(
            {
                "kanun": kanun,
                "kanun_no": kanun_no_bul(
                    kanun
                ),
                "madde": madde,
                "madde_turu": madde_turu
            }
        )


    embeddings = model.encode(
        documents,
        show_progress_bar=False
    ).tolist()


    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )


    print(
        f"{min(baslangic + batch_size, len(dataset))}"
        f" / {len(dataset)} kayıt işlendi."
    )


print(
    "TÜM KAYITLAR CHROMADB'YE EKLENDİ."
)

print(
    "ChromaDB kayıt sayısı:",
    collection.count()
)