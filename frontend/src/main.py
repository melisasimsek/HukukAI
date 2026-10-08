from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import chromadb
import re

from llm import hukuk_cevapla

app = FastAPI(title="HukukAI", version="1.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Embedding modeli yukleniyor...")
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
print("Embedding modeli hazir.")

client = chromadb.PersistentClient(path="../models/chroma_db_yeni")
collection = client.get_collection("hukuk_kanunlari")
print("ChromaDB baglantisi hazir.")
print("ChromaDB kayit sayisi:", collection.count())

# ============================================================
# KRİTİK MADDELER İÇİN DOĞRUDAN ERİŞİM
# ============================================================

tum_kayitlar = collection.get(
    include=[
        "metadatas",
        "documents"
    ]
)

DIRECT_ARTICLES = {}

for document, metadata in zip(
    tum_kayitlar["documents"],
    tum_kayitlar["metadatas"]
):
    kanun = metadata.get("kanun", "")
    madde = metadata.get("madde")

    if kanun is not None and madde is not None:
        if kanun.lower().endswith(".pdf"):
            kanun = kanun[:-4]

        DIRECT_ARTICLES[
            (
                kanun.split()[0],
                str(madde)
            )
        ] = {
            "kanun": kanun,
            "madde": madde,
            "icerik": document,
            "mesafe": 0.0,
            "skor": 999999
        }

print(
    "Dogrudan madde erisimi hazir:",
    len(DIRECT_ARTICLES)
)


class Soru(BaseModel):
    soru: str


def normalize(text):
    return text.lower().casefold()


def kelimeler(text):
    return set(re.findall(r"[a-zA-Z0-9çğıöşüÇĞİÖŞÜ]+", normalize(text)))


def keyword_score(question, document):
    stop_words = {
        "bir", "bu", "şu", "ve", "veya", "ile", "için", "göre",
        "mi", "mı", "mu", "mü", "ne", "nasıl", "neden", "hangi",
        "olan", "midir", "mudur", "özel", "sektör"
    }
    q = {x for x in kelimeler(question) if x not in stop_words}
    d = kelimeler(document)
    return len(q.intersection(d))


def concept_score(question, document):
    q = normalize(question)
    d = normalize(document)
    groups = [
        ["hafta tatili", "haftalık dinlenme", "kesintisiz", "24 saat", "yirmidört saat", "dinlenme"],
        ["deneme", "deneme süresi", "deneme kaydı"],
        ["yıllık izin", "yıllık ücretli izin", "izin hakkı"],
        ["ücret", "maaş", "ödeme"],
        ["miras", "mirasçı", "yasal mirasçı", "mirasbırakan"],
        ["kişisel veri", "kişisel veriler", "açık rıza", "veri sorumlusu"],
        ["tüketici", "ayıplı mal", "ayıplı hizmet"],
        ["suç", "hırsızlık", "dolandırıcılık", "ceza"],
    ]
    score = 0
    for group in groups:
        if any(term in q for term in group):
            for term in group:
                if term in d:
                    score += 5 if " " in term else 2
    return score


def article_number(metadata, document):
    value = metadata.get("madde")
    if value is None:
        value = metadata.get("madde_no")
    if value is not None:
        return value
    match = re.search(r"Madde\s+(\d+)", document, re.IGNORECASE)
    return int(match.group(1)) if match else None


def clean_law_name(value):
    if not value:
        return "Bilinmeyen mevzuat"
    return value[:-4] if value.lower().endswith(".pdf") else value


def preferred_articles_lookup(question):
    q = normalize(question)
    target_articles = []

    # 4857 İş Kanunu
    if "deneme" in q:
        target_articles.append(("4857", "15"))
    if any(term in q for term in ["7 gün", "yedi gün", "hafta tatili", "aralıksız", "dinlenme"]):
        target_articles.append(("4857", "46"))
    if any(term in q for term in ["yıllık ücretli izin", "yıllık izin hakkı", "yıllık izin", "izin"]):
        target_articles.append(("4857", "53"))
    if any(term in q for term in ["haftada 6 gün", "6 gün çalış", "altı gün çalış", "çalışma süresi"]):
        target_articles.append(("4857", "63"))

    # 4721 Türk Medeni Kanunu (Miras)
    if any(term in q for term in ["yasal mirasçı", "yasal mirasçılar", "mirasçılar", "miras kimlere kalır", "mirasçı"]):
        target_articles.extend([
            ("4721", "495"),
            ("4721", "496"),
            ("4721", "497"),
            ("4721", "499")
        ])

    # 6698 KVKK
    if any(term in q for term in ["açık rıza", "kişisel veri", "kişisel veriler", "veri sorumlusu"]):
        target_articles.extend([("6698", "5"), ("6698", "6")])

    # 6502 Tüketici Kanunu
    if any(term in q for term in ["ayıplı mal", "ayıplı ürün", "ayıplı hizmet", "tüketici hakları"]):
        target_articles.append(("6502", "11"))

    # 5237 TCK
    if "hırsızlık" in q: target_articles.append(("5237", "141"))
    if "dolandırıcılık" in q: target_articles.append(("5237", "157"))
    if "hakaret" in q: target_articles.append(("5237", "125"))
    if "tehdit" in q: target_articles.append(("5237", "106"))

    matched = []
    seen = set()
    for kanun, madde in target_articles:
        key = (kanun, str(madde))
        if key in DIRECT_ARTICLES and key not in seen:
            matched.append(DIRECT_ARTICLES[key])
            seen.add(key)

    return matched


def retrieve(question):
    embedding = model.encode(question).tolist()

    result = collection.query(
        query_embeddings=[embedding],
        n_results=min(100, collection.count()),
        include=["metadatas", "documents", "distances"]
    )

    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]

    candidates = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        law = clean_law_name(meta.get("kanun", ""))
        article = article_number(meta, doc)
        semantic_score = 1 / (1 + float(dist))
        score = (
            semantic_score * 10
            + keyword_score(question, doc) * 4
            + concept_score(question, doc)
        )
        candidates.append({
            "kanun": law,
            "madde": article,
            "icerik": doc,
            "mesafe": float(dist),
            "skor": score
        })

    candidates.sort(key=lambda item: item["skor"], reverse=True)

    preferred_list = preferred_articles_lookup(question)
    if preferred_list:
        pref_keys = {(p["kanun"].split()[0], str(p["madde"])) for p in preferred_list}
        other_candidates = [
            c for c in candidates
            if (c["kanun"].split()[0], str(c["madde"])) not in pref_keys
        ]
        return (preferred_list + other_candidates)[:6]

    return candidates[:6]


def build_context(results):
    parts = []
    for index, item in enumerate(results, start=1):
        parts.append(
            f"KAYNAK {index}\n\n"
            f"KANUN:\n{item['kanun']}\n\n"
            f"MADDE:\n{item['madde']}\n\n"
            f"MADDE METNİ:\n{item['icerik']}"
        )
    return "\n\n" + ("\n" + "=" * 70 + "\n\n").join(parts)


def cevap_uret(question):
    question = question.strip()
    if not question:
        return {"cevap": "Lütfen bir hukuk sorusu yazın.", "kaynaklar": []}

    results = retrieve(question)
    if not results:
        return {"cevap": "Sorunuzla ilgili mevzuat kaynağı bulunamadı.", "kaynaklar": []}

    context = build_context(results)
    try:
        answer = hukuk_cevapla(question, context)
    except Exception as error:
        print("Gemini hatasi:", error)
        answer = "Gemini cevap uretemedi. Lutfen tekrar deneyin."

    sources = [
        {"kanun": item["kanun"], "madde": item["madde"], "icerik": item["icerik"]}
        for item in results
    ]
    return {"cevap": answer, "kaynaklar": sources}


@app.get("/")
def root():
    return {
        "mesaj": "HukukAI calisiyor.",
        "durum": "RAG + Gemini aktif",
        "versiyon": "1.4.0",
        "chroma_kayit": collection.count()
    }


@app.post("/sor")
def sor(soru: Soru):
    return cevap_uret(soru.soru)