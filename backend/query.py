import chromadb
import json
import re
from sentence_transformers import SentenceTransformer
from llm import hukuk_cevapla

print("Model yükleniyor...")

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

print("Model hazır.")

client = chromadb.PersistentClient(path="../models/chroma_db_yeni")
collection = client.get_collection("hukuk_kanunlari")

with open("../dataset/hukuk_dataset.json", "r", encoding="utf-8") as f:
    dataset = json.load(f)


def cevap_uret(soru):

    # --------------------------------------------------
    # 1. Kullanıcı doğrudan kanun + madde numarası verdiyse
    # --------------------------------------------------

    kanun = re.search(r"(4857|4721|2709)", soru)
    madde = re.search(r"(\d+)\.?\s*madd", soru.lower())

    if kanun and madde:

        kanun_no = kanun.group(1)
        madde_no = int(madde.group(1))

        for kayit in dataset:

            if (
                kanun_no in kayit["kanun"]
                and kayit["madde_no"] == madde_no
            ):

                belge = f"""
Kanun: {kayit['kanun']}
Madde: {kayit['madde_no']}

{kayit['icerik']}
"""

                cevap = hukuk_cevapla(soru, belge)

                return {
                    "cevap": cevap,
                    "kaynaklar": [
                        {
                            "kanun": kayit["kanun"],
                            "madde": kayit["madde_no"]
                        }
                    ]
                }

    # --------------------------------------------------
    # 2. Sorunun hangi hukuk alanıyla ilgili olduğunu bul
    # --------------------------------------------------

    soru_lower = soru.lower()

    is_hukuku = any(kelime in soru_lower for kelime in [
        "işçi",
        "işveren",
        "çalışan",
        "çalışma",
        "iş",
        "izin",
        "maaş",
        "ücret",
        "kıdem",
        "ihbar",
        "deneme",
        "iş sözleşmesi",
        "yıllık ücretli izin"
    ])

    medeni_hukuk = any(kelime in soru_lower for kelime in [
        "miras",
        "mirasçı",
        "mirasbırakan",
        "evlilik",
        "evlenme",
        "boşanma",
        "eş",
        "velayet",
        "çocuk",
        "soybağı"
    ])

    anayasa = any(kelime in soru_lower for kelime in [
        "anayasa",
        "temel hak",
        "özgürlük",
        "cumhurbaşkanı",
        "meclis",
        "milletvekili",
        "seçim"
    ])

    # --------------------------------------------------
    # 3. Embedding araması
    # --------------------------------------------------

    embedding = model.encode(soru).tolist()

    sonuc = collection.query(
        query_embeddings=[embedding],
        n_results=15,
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    belgeler = ""
    kaynaklar = []
    eklenen = set()

    print("\nBulunan maddeler:")

    # --------------------------------------------------
    # 4. Sonuçları filtrele
    # --------------------------------------------------

    for i in range(len(sonuc["documents"][0])):

        meta = sonuc["metadatas"][0][i]
        distance = sonuc["distances"][0][i]

        kanun = meta["kanun"]
        madde = meta["madde"]

        print(
            f"Madde: {madde} | "
            f"Mesafe: {distance:.4f} | "
            f"Kanun: {kanun}"
        )

        # Madde 0 kanun giriş bilgileridir.
        # Hukuki sorular için kaynak olarak kullanma.
        if madde == 0:
            continue

        # --------------------------------------------------
        # İş hukuku
        # --------------------------------------------------

        if is_hukuku and "4857" not in kanun:
            continue

        # --------------------------------------------------
        # Medeni hukuk
        # --------------------------------------------------

        if medeni_hukuk and "4721" not in kanun:
            continue

        # --------------------------------------------------
        # Anayasa
        # --------------------------------------------------

        if anayasa and "Anayasası" not in kanun:
            continue

        anahtar = (kanun, madde)

        if anahtar in eklenen:
            continue

        eklenen.add(anahtar)

        kaynaklar.append({
            "kanun": kanun,
            "madde": madde
        })

        belgeler += f"""
Kanun: {kanun}
Madde: {madde}

{sonuc["documents"][0][i]}

"""

        # En fazla 3 kaynak
        if len(kaynaklar) >= 3:
            break

    # --------------------------------------------------
    # 5. Kaynak bulunamadıysa
    # --------------------------------------------------

    if not kaynaklar:

        return {
            "cevap": "Bu soruyla ilgili uygun bir mevzuat maddesi bulunamadı.",
            "kaynaklar": []
        }

    # --------------------------------------------------
    # 6. LLM'e gönder
    # --------------------------------------------------

    cevap = hukuk_cevapla(
        soru,
        belgeler
    )

    return {
        "cevap": cevap,
        "kaynaklar": kaynaklar
    }