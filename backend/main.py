from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import chromadb
import os
import re
import time
import html
import io
from docx import Document
from docx.shared import Pt
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from llm import hukuk_cevapla, dilekce_olustur


app = FastAPI(
    title="HukukAI",
    version="1.8.0",
)
@app.get("/health")
def health_check():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# EMBEDDING + CHROMADB
# ============================================================

print("Embedding modeli yukleniyor...")

model = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

print("Embedding modeli hazir.")

client = chromadb.PersistentClient(
    path="../models/chroma_db"
)

collection = client.get_collection(
    "hukuk_kanunlari"
)

print("ChromaDB baglantisi hazir.")
print(
    "ChromaDB kayit sayisi:",
    collection.count(),
)


# ============================================================
# DOGRUDAN MADDE ERISIMI
# ============================================================

tum_kayitlar = collection.get(
    include=[
        "metadatas",
        "documents",
    ]
)

DIRECT_ARTICLES = {}

for document, metadata in zip(
    tum_kayitlar["documents"],
    tum_kayitlar["metadatas"],
):
    if metadata.get("madde_turu") != "NORMAL MADDE":
        continue

    document = html.unescape(document or "")
    kanun = metadata.get(
        "kanun",
        "",
    )

    madde = metadata.get(
        "madde"
    )

    if kanun is None or madde is None:
        continue

    if kanun.lower().endswith(".pdf"):
        kanun = kanun[:-4]

    law_number = kanun.split()[0]

    DIRECT_ARTICLES[
        (
            law_number,
            str(madde),
        )
    ] = {
        "kanun": kanun,
        "kanun_no": law_number,
        "madde": madde,
        "icerik": document,
        "mesafe": 0.0,
        "skor": 999999,
        "oncelikli": True,
    }


print(
    "Dogrudan madde erisimi hazir:",
    len(DIRECT_ARTICLES),
)

# ============================================================
# API MODEL
# ============================================================

class Soru(BaseModel):
    soru: str
class DilekceIstegi(BaseModel):
    soru: str
    cevap: str

class DilekceDosyaIstegi(BaseModel):
    baslik: str
    dilekce: str



# ============================================================
# YARDIMCI FONKSIYONLAR
# ============================================================

def normalize(text):
    if text is None:
        return ""

    text = str(text)

    # Türkçe büyük I/İ harflerini doğru küçült
    text = text.replace("İ", "i").replace("I", "ı")

    return text.lower()


def kelimeler(text):
    return set(
        re.findall(
            r"[a-zA-Z0-9çğıöşüÇĞİÖŞÜ]+",
            normalize(text),
        )
    )
def keyword_score(
    question,
    document,
):
    stop_words = {
        "bir",
        "bu",
        "şu",
        "ve",
        "veya",
        "ile",
        "için",
        "göre",
        "mi",
        "mı",
        "mu",
        "mü",
        "ne",
        "nasıl",
        "neden",
        "hangi",
        "olan",
        "midir",
        "mudur",
        "özel",
        "sektör",
        "kalır",
    }

    q = {
        word
        for word in kelimeler(question)
        if word not in stop_words
    }

    d = kelimeler(document)

    score = 0

    for q_word in q:

        # Önce birebir kelime eşleşmesi
        if q_word in d:
            score += 1
            continue

        # Uzun kelimelerde kontrollü prefix eşleşmesi
        if len(q_word) >= 5:
            for d_word in d:
                if (
                    len(d_word) >= 5
                    and (
                        d_word.startswith(q_word)
                        or q_word.startswith(d_word)
                    )
                ):
                    score += 1
                    break

    return score
def intent_keyword_score(question, intent_name):
    description = INTENT_PROTOTYPES[intent_name][0]

    generic_words = {
        "iş",
        "işçi",
        "işçinin",
        "işveren",
        "işverenin",
        "işten",
        "süre",
        "süresi",
        "hakkı",
        "hak",
        "kişisel",
        "veri",
        "veriler",
        "miras",
        "kişi",
        "kişinin",
        "nedenle",
        "nedeniyle",
        "bu",
        "miyim",
        "çıkarmadan",
        "çıkarması",
        "ve",
        "sözleşmemi",
        "feshedebilir",
        "bir",
        "başka",
        "olmadan",
        "telefon",
    }

    q_words = {
        word
        for word in kelimeler(question)
        if word not in generic_words
    }

    intent_words = kelimeler(description)

    score = 0

    for q_word in q_words:
        if q_word in intent_words:
            score += 1
            continue

        if len(q_word) >= 5:
            for intent_word in intent_words:
                if (
                    len(intent_word) >= 5
                    and q_word[:5] == intent_word[:5]
                ):
                    score += 1
                    break

    return score
def title_score(question, document):
    if not document:
        return 0

    lines = document.splitlines()

    if not lines:
        return 0

    title = normalize(lines[0])
    q = normalize(question)

    score = 0

    important_terms = [
        "haklı",
        "derhal",
        "fesih",
        "izin",
        "ücret",
        "miras",
        "tüketici",
        "kişisel veri",
        "hakaret",
        "tehdit",
    ]

    q_words = set(kelimeler(question))
    title_words = set(kelimeler(lines[0]))

    for term in important_terms:
        if " " not in term:
            if term in q_words and term in title_words:
                score += 3

    phrases = [
        "haklı nedenle",
        "derhal fesih",
        "yıllık ücretli izin",
        "hafta tatili",
        "kişisel veri",
    ]

    for phrase in phrases:
        if phrase in q and phrase in title:
            score += 6

    # Hukuki işlemi yapan tarafı ayrıca ayırt et.
    if "işveren" in q:
        if "işveren" in title:
            score += 15

        if "işçinin" in title:
            score -= 10

    elif "işçi" in q:
        if "işçinin" in title:
            score += 15

        if "işveren" in title:
            score -= 10

    return score


def concept_score(
    question,
    document,
):
    q = normalize(question)
    d = normalize(document)

    groups = [
        [
            "hafta tatili",
            "haftalık dinlenme",
            "kesintisiz",
            "24 saat",
            "yirmidört saat",
            "dinlenme",
        ],
        [
            "deneme",
            "deneme süresi",
            "deneme kaydı",
        ],
        [
            "yıllık izin",
            "yıllık ücretli izin",
            "izin hakkı",
        ],
        [
            "ücret",
            "maaş",
            "ödeme",
        ],
        [
    "mirasçı",
    "yasal mirasçı",
    "mirasbırakan",
    "tereke",
    "altsoy",
    "sağ kalan eş",
],
        [
            "kişisel veri",
            "kişisel veriler",
            "açık rıza",
            "veri sorumlusu",
            "veri işleme",
        ],
        [
            "tüketici",
            "ayıplı mal",
            "ayıplı ürün",
            "ayıplı hizmet",
            "seçimlik hak",
        ],
        [
            "suç",
            "hırsızlık",
            "dolandırıcılık",
            "ceza",
        ],
        [
            "hakaret",
            "küfür",
            "onur",
            "şeref",
        ],
        [
            "tehdit",
            "korkutma",
        ],
    ]

    score = 0

    q_words = kelimeler(question)
    d_words = kelimeler(document)

    for group in groups:
        for term in group:
            if " " in term:
                if term in q and term in d:
                    score += 5
            else:
                if term in q_words and term in d_words:
                    score += 2

    return score


def article_number(
    metadata,
    document,
):
    value = metadata.get(
        "madde"
    )

    if value is None:
        value = metadata.get(
            "madde_no"
        )

    if value is not None:
        return value

    match = re.search(
        r"Madde\s+(\d+)",
        document,
        re.IGNORECASE,
    )

    if match:
        return int(
            match.group(1)
        )

    return None


def clean_law_name(value):
    if not value:
        return "Bilinmeyen mevzuat"

    if value.lower().endswith(
        ".pdf"
    ):
        return value[:-4]

    return value


def get_law_number(
    law_name,
):
    if not law_name:
        return ""

    parts = str(
        law_name
    ).split()

    if not parts:
        return ""

    return parts[0]


def article_key(item):
    return (
        str(
            item.get(
                "kanun_no",
                get_law_number(
                    item.get(
                        "kanun",
                        "",
                    )
                ),
            )
        ),
        str(
            item.get(
                "madde",
                "",
            )
        ),
    )


def unique_results(results):
    unique = []
    seen = set()

    for item in results:
        key = article_key(
            item
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


# ============================================================
# HALK DILI -> HUKUKI SORGU GENISLETME
# ============================================================

INTENT_PROTOTYPES = {
"tuketici_ayipli_mal": (
    "Satın alınan telefon bilgisayar elektronik cihaz veya başka bir ürünün "
    "bozuk arızalı kusurlu ayıplı çıkması, çalışmaması, kısa sürede bozulması, "
    "satıcıdan iade değişim ücretsiz onarım veya bedel indirimi istenmesi",
    "6502 Tüketicinin Korunması Hakkında Kanun ayıplı mal arızalı ürün "
    "bozuk telefon kusurlu ürün satıcı değişim iade seçimlik haklar ücretsiz onarım"
),
    # IS HUKUKU
    "hafta_tatili": (
        "İşçinin aralıksız her gün çalıştırılması, boş gün veya haftalık dinlenme verilmemesi",
        "hafta tatili haftalık dinlenme işçi kesintisiz 24 saat"
    ),
    "deneme_suresi": (
        "İşe yeni başlayan işçinin deneme dönemi ve deneme süreli iş sözleşmesi",
        "deneme süresi deneme kaydı iş sözleşmesi"
    ),
    "yillik_izin": (
        "İşçinin yıllık ücretli izin hakkı ve izin günleri",
        "yıllık ücretli izin işçi izin hakkı"
    ),
    "ihbar_suresi": (
    "İş sözleşmesinin feshedilmesinde ihbar süresi, bildirim süresi ve önceden haber verme süresi",
    "4857 İş Kanunu ihbar süresi bildirim süresi süreli fesih iş sözleşmesi"
),
"isci_hakli_fesih": (
    "İşçinin kendisinin iş sözleşmesini haklı nedenle feshetmek istemesi, "
    "işçinin sözleşmesini sona erdirip işten ayrılıp ayrılamayacağını sorması; "
    "işverenin ücret veya maaş ödememesi, kötü davranması, hakaret veya tacizde "
    "bulunması gibi nedenlerle işçinin kendi sözleşmesini bildirim süresini "
    "beklemeden haklı nedenle derhal feshetmesi",
    "4857 İş Kanunu Madde 24 işçinin haklı nedenle derhal fesih hakkı "
    "işçinin kendi iş sözleşmesini feshetmesi işçinin işten ayrılması "
    "maaş ücret ödenmemesi işverenin kötü davranışı hakaret taciz"
),"isveren_hakli_fesih": (
        "İşverenin işçiyi haklı nedenle derhal işten çıkarması, iş sözleşmesini bildirim süresini beklemeden feshetmesi, işverenin derhal fesih hakkı",
        "4857 İş Kanunu işveren haklı nedenle derhal fesih işten çıkarma iş sözleşmesinin feshi sağlık sebepleri ahlak iyi niyet zorlayıcı sebep"
    ),
    # MIRAS
    "miras_mirascilar": (
        "Bir kişi öldüğünde mirasının kimlere kalacağı, kimlerin yasal mirasçı olduğu, "
        "çocukların, altsoyun, anne babanın ve diğer hısımların mirasçı olması",
        "4721 Türk Medeni Kanunu yasal mirasçılar altsoy çocuklar "
        "ana baba mirasçı mirasbırakan"
    ),

        "miras_es_payi": (
        "Ölen kişinin geride kalan karısının veya kocasının, yani sağ kalan eşin "
        "mirasın ne kadarını alacağı ve eşin miras oranı",
        "4721 Türk Medeni Kanunu sağ kalan eş eşin miras payı "
        "eşin miras oranı dörtte bir yarısı dörtte üç"
    ),

        "miras_sakli_pay": (
        "Saklı pay nedir, saklı paylı mirasçılar kimlerdir ve saklı pay oranları nelerdir",
        "4721 Türk Medeni Kanunu saklı pay saklı paylı mirasçı "
        "saklı pay oranı tasarruf edilebilir kısım"
    ),
        "miras_mirastan_cikarma": (
        "Bir kişinin mirasçılıktan çıkarılması, mirastan çıkarılması, miras payı alamaması "
        "ve mirasçılıktan çıkarılan kişinin veya altsoyunun hakları",
        "4721 Türk Medeni Kanunu mirasçılıktan çıkarma mirastan çıkarma "
        "miras payı altsoy yasal mirasçı"
    ),
    # KISISEL VERILER
    "kisisel_veri": (
    "Kişisel veri kavramı, kişisel verilerin işlenmesi, açık rıza ve veri sorumlusuna ilişkin genel konular",
    "6698 KVKK kişisel veri veri işleme açık rıza veri sorumlusu"
),
    "kisisel_veri_aktarim": (
    "Bir kişinin kişisel bilgilerinin izni veya rızası olmadan başka bir kişiye "
    "gönderilmesi, paylaşılması, açıklanması, aktarılması veya üçüncü kişilere verilmesi",
    "6698 KVKK kişisel verilerin aktarılması izinsiz paylaşım rıza olmadan paylaşma "
    "üçüncü kişiye aktarma veri paylaşımı"
),

"kisisel_veri_haklari": (
    "Kişisel verileri işlenen kişinin hangi haklara sahip olduğu; verilerinin "
    "silinmesini veya düzeltilmesini istemesi, verilerinin işlenip işlenmediğini "
    "öğrenmesi, bilgi talep etmesi veya veri sorumlusuna başvurması",
    "6698 KVKK ilgili kişinin hakları kişisel verileri silme düzeltme "
    "bilgi isteme öğrenme veri sorumlusuna başvuru"
),

    # CEZA HUKUKU
    "hirsizlik": (
        "Telefon para eşya veya başka bir malın sahibinin rızası olmadan alınması veya çalınması",
        "hırsızlık taşınır mal zilyet rıza suç"
    ),
    "dolandiricilik": (
        "Hile kandırma sahte ilan veya benzeri yollarla bir kişinin parasının alınması",
        "dolandırıcılık hile yarar zarar suç"
    ),
    "hakaret": (
        "Bir kişiye küfür edilmesi aşağılanması veya onur şeref ve saygınlığının rencide edilmesi",
        "hakaret onur şeref saygınlık suç"
    ),
    "tehdit": (
        "Bir kişinin öldürmek yaralamak veya zarar vermekle korkutulması",
        "tehdit korkutma zarar verme suç"
    ),

    # KAT MULKIYETI
    "apartman_aidati": (
        "Apartman site aidatının ortak giderlerin veya gider avansının ödenmemesi, aidat borcu ve yönetici",
        "634 Kat Mülkiyeti Kanunu ortak gider gider avansı aidat borcu kat maliki yönetici"
    ),

    # TRAFIK
    "trafik_kazasi": (
        "Trafik kazası yapılması, kazaya karışan sürücünün yükümlülükleri ve olay yerinden ayrılması",
        "2918 Karayolları Trafik Kanunu trafik kazası sürücü kaza yükümlülükleri"
    ),
    "trafik_cezasi": (
        "Trafik cezası, hız sınırı, ehliyet, sürücü belgesi veya trafik kurallarına aykırılık",
        "2918 Karayolları Trafik Kanunu trafik cezası sürücü belgesi hız trafik kuralları"
    ),

    # KIRA
    "kira": (
        "Ev sahibi kiracı kira sözleşmesi kira bedeli tahliye depozito ve kiralanan konutla ilgili uyuşmazlık",
        "6098 Türk Borçlar Kanunu kira kiracı kiraya veren kira sözleşmesi tahliye kira bedeli"
    ),
        "kira_artisi": (
        "Konut veya işyeri kirasında kira bedelinin artırılması, kira artış oranı, "
        "ev sahibinin kira bedelini yükseltmek istemesi ve yeni kira bedelinin belirlenmesi",
        "6098 Türk Borçlar Kanunu kira bedelinin belirlenmesi kira artışı "
        "kira bedeli artış oranı kiraya veren kiracı"
    ),

    # ICRA
    "icra": (
        "Borç nedeniyle icra takibi yapılması, ödeme emri, haciz veya borcun icra yoluyla tahsil edilmesi",
        "2004 İcra ve İflas Kanunu icra takibi ödeme emri haciz alacak borç"
    ),

    # MEMUR
    "devlet_memuru": (
        "Devlet memurunun hakları görevleri izinleri disiplin işlemleri veya memuriyete ilişkin uyuşmazlık",
        "657 Devlet Memurları Kanunu memur izin disiplin görev hak"
    ),

    # SOSYAL GUVENLIK
    "sgk": (
        "Sigortalılık emeklilik prim iş kazası sosyal güvenlik veya SGK ile ilgili haklar",
        "5510 Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu sigorta prim emeklilik iş kazası"
    ),
        # SOSYAL GÜVENLİK KURUMU
    "sgk_kurum": (
    "Sosyal Güvenlik Kurumunun görevleri yetkileri amacı teşkilatı ve sorumlulukları",
    "4 Cumhurbaşkanlığı Kararnamesi Sosyal Güvenlik Kurumu SGK kurum görev yetki"
),

    # TAPU

    # TAPU
    "tapu": (
        "Tapu kaydı taşınmazın tescili mülkiyet devri veya tapu siciliyle ilgili işlemler",
        "2644 Tapu Kanunu tapu taşınmaz tescil mülkiyet"
    ),

    # IMAR
    "imar": (
        "Kaçak yapı ruhsat imar planı yapı izni veya belediyenin imar işlemleri",
        "3194 İmar Kanunu imar yapı ruhsatı kaçak yapı imar planı"
    ),

    # KAMULASTIRMA
    "kamulastirma": (
        "Devletin veya kamu kurumunun özel mülkiyetteki taşınmaza el koyması, kamulaştırma ve bedel",
        "2942 Kamulaştırma Kanunu kamulaştırma taşınmaz kamulaştırma bedeli"
    ),

    # YABANCILAR
    "yabancilar": (
        "Yabancı kişinin Türkiye'de ikamet etmesi, ikamet izni, sınır dışı edilmesi veya uluslararası koruma",
        "6458 Yabancılar ve Uluslararası Koruma Kanunu ikamet izni yabancı sınır dışı uluslararası koruma"
    ),

    # ARABULUCULUK
    "arabuluculuk": (
        "Uyuşmazlığın dava açmadan arabulucu ile çözülmesi veya zorunlu arabuluculuk süreci",
        "6325 Hukuk Uyuşmazlıklarında Arabuluculuk Kanunu arabuluculuk uyuşmazlık anlaşma"
    ),

    # AILE ICI SIDDET
    "aile_ici_siddet": (
        "Eş sevgili veya aile üyesi tarafından şiddet tehdit takip veya taciz uygulanması ve korunma talebi",
        "6284 şiddetin önlenmesi koruyucu önleyici tedbir uzaklaştırma"
    ),

    # ENGELLI HAKLARI
    "engelli_haklari": (
        "Engelli kişinin ayrımcılığa uğraması, erişilebilirlik veya engellilere tanınan haklar",
        "5378 Engelliler Hakkında Kanun engelli hakları erişilebilirlik ayrımcılık"
    ),

    # BILISIM VE INTERNET
    "internet": (
        "İnternet sitesi içerik sağlayıcı erişim engelleme veya internet ortamındaki hukuki sorumluluk",
        "5651 internet içerik sağlayıcı yer sağlayıcı erişimin engellenmesi"
    ),
    
    
    
    # ELEKTRONIK TICARET
    "e_ticaret": (
        "İnternetten satış elektronik ticaret ticari elektronik ileti veya istenmeyen reklam mesajları",
        "6563 Elektronik Ticaret elektronik ileti ticari ileti internet satış"
    ),
}


# ============================================================
# INTENT HUKUK ALANLARI
# ============================================================

INTENT_GROUPS = {
    # İş hukuku
    "hafta_tatili": "is_hukuku",
    "deneme_suresi": "is_hukuku",
    "yillik_izin": "is_hukuku",
    "ihbar_suresi": "is_hukuku",
    "isci_hakli_fesih": "is_hukuku",
    "isveren_hakli_fesih": "is_hukuku",

    # Miras hukuku
    "miras_mirascilar": "miras",
    "miras_es_payi": "miras",
    "miras_sakli_pay": "miras",
    "miras_mirastan_cikarma": "miras",

    # Kişisel veriler
    "kisisel_veri": "kvkk",
    "kisisel_veri_aktarim": "kvkk",
    "kisisel_veri_haklari": "kvkk",

    # Ceza hukuku
    "hirsizlik": "ceza",
    "dolandiricilik": "ceza",
    "hakaret": "ceza",
    "tehdit": "ceza",

    # Sosyal güvenlik
    "sgk": "sosyal_guvenlik",
    "sgk_kurum": "sosyal_guvenlik",
    # Kira hukuku
    "kira": "kira_hukuku",
    "kira_artisi": "kira_hukuku",
}
GENERAL_INTENTS = {
    "kisisel_veri",
    "sgk",
}
MUTUALLY_EXCLUSIVE_INTENTS = {
    frozenset({
        "isci_hakli_fesih",
        "isveren_hakli_fesih",
    }),
}
print("Semantik niyet modeli hazirlaniyor...")

INTENT_NAMES = list(INTENT_PROTOTYPES)
INTENT_EMBEDDINGS = model.encode([INTENT_PROTOTYPES[n][0] for n in INTENT_NAMES], normalize_embeddings=True)
print("Semantik niyet modeli hazir.")
def detect_semantic_intents(question, threshold=0.43, max_intents=2):
    qemb = model.encode(question, normalize_embeddings=True)

    scored = sorted(
        ((n, float(qemb @ e)) for n, e in zip(INTENT_NAMES, INTENT_EMBEDDINGS)),
        key=lambda x: x[1],
        reverse=True
    )

    if not scored or scored[0][1] < threshold:
        return []
        # Birinci intent seçiminde embedding skorunun yanında
    # sorudaki kelime kanıtını da değerlendir.
    top_candidates = []

    for name, score in scored:
        evidence_score = intent_keyword_score(question, name)

        # Normal durumda semantik eşik 0.43.
        # Ancak soruda güçlü kelime kanıtı varsa daha düşük
        # semantik skorlu intentleri de aday olarak değerlendir.
        evidence_score = intent_keyword_score(question, name)

        if score < threshold:
            if not (evidence_score >= 2 and score >= 0.20):
                continue

        top_candidates.append(
            (name, score, evidence_score)
        )
    top_candidates.sort(
    key=lambda x: (x[2], x[1]),
    reverse=True
)
        # Birbirine rakip intentler varsa, aralarındaki anlamsal farkı da dikkate al.
    for conflict_group in MUTUALLY_EXCLUSIVE_INTENTS:
        conflict_candidates = [
            candidate
            for candidate in top_candidates
            if candidate[0] in conflict_group
        ]

        if len(conflict_candidates) >= 2:
            conflict_candidates.sort(
                key=lambda x: x[1],
                reverse=True
            )

            semantic_best = conflict_candidates[0]
            evidence_best = max(
                conflict_candidates,
                key=lambda x: (x[2], x[1])
            )

            # Semantik olarak öndeki intentin de kelime kanıtı varsa
            # ve iki intent birbirine yakınsa semantik anlamı tercih et.
            if (
                semantic_best[2] > 0
                and semantic_best[1] - evidence_best[1] >= 0
                and semantic_best[1] - evidence_best[1] <= 0.10
            ):
                top_candidates.remove(semantic_best)
                top_candidates.insert(0, semantic_best)

    best_name, best_score, best_evidence = top_candidates[0]

    selected = [
        (best_name, best_score)
    ]

    best_group = INTENT_GROUPS.get(best_name)

       # Uygun ikinci intent adaylarını burada topla.
    candidates = []

    for name, score in scored:
        if name == best_name:
            continue

        evidence_score = intent_keyword_score(question, name)

        if score < threshold:
            if not (evidence_score >= 2 and score >= 0.20):
                continue
        # Genel intentleri ikinci intent olarak alma.
        if name in GENERAL_INTENTS:
            continue

        # Ana intent ile aynı hukuk alanında olmalı.
        if best_group is None or INTENT_GROUPS.get(name) != best_group:
            continue

        # Soruda intenti destekleyen kelime kanıtını hesapla.
        evidence_score = intent_keyword_score(question, name)

        if evidence_score <= 0:
            continue

        candidates.append(
            (name, score, evidence_score)
        )

    # Kelime kanıtı daha güçlü olan intent önce gelsin.
    candidates.sort(
        key=lambda x: (x[2], x[1]),
        reverse=True
    )

    for name, score, evidence_score in candidates:

        conflict = any(
            frozenset({selected_name, name}) in MUTUALLY_EXCLUSIVE_INTENTS
            for selected_name, _ in selected
        )

        if conflict:
            continue

        if len(selected) >= max_intents:
            break

        selected.append((name, score))

    return selected
def expand_query(question, semantic_intents=None):
    q = normalize(question)

    concept_map = {
        "ayıplı mal tüketici seçimlik haklar iade değişim ücretsiz onarım": [
            "bozuk çıktı",
            "ürün bozuk",
            "telefon bozuk",
            "çalışmıyor",
            "çalışmıyo",
            "değiştirmiyor",
            "değiştirmiyolar",
            "değiştirmiyorlar",
            "iade almıyor",
            "iade almıyolar",
            "geri almıyor",
            "paramı vermiyor",
            "kusurlu çıktı",
        ],

        "hafta tatili haftalık dinlenme işçi kesintisiz 24 saat": [
            "izin yok",
            "izin vermiyor",
            "izin vermiyo",
            "7 gündür çalış",
            "7 gün çalış",
            "her gün çalış",
            "dinlenmeden çalış",
        ],

        "deneme süresi deneme kaydı iş sözleşmesi": [
            "deneme süresi",
            "deneme dönemi",
            "denemedeyim",
            "işe yeni başladım",
        ],

        "yıllık ücretli izin işçi izin hakkı": [
            "yıllık izin",
            "senelik izin",
            "izin hakkım",
            "kaç gün izin",
        ],

       
        "kişisel veri açık rıza veri işleme veri sorumlusu KVKK": [
            "bilgilerimi izinsiz",
            "verilerimi izinsiz",
            "iznim olmadan bilgilerimi",
            "telefon numaramı paylaştı",
            "adresimi paylaştı",
            "kişisel bilgilerimi paylaştı",
            "fotomu izinsiz",
            "fotoğrafımı izinsiz",
        ],

        "hırsızlık taşınır mal zilyet rıza suç": [
            "telefonumu çaldı",
            "telefonumu çaldılar",
            "telefonum çalındı",
            "paramı çaldı",
            "eşyamı çaldı",
            "çalındı",
            "çalmak",
        ],

        "dolandırıcılık hile yarar zarar suç": [
            "dolandırıldım",
            "kandırıp paramı aldı",
            "kandırdı paramı aldı",
            "sahte ilan",
            "para gönderdim kayboldu",
        ],

        "hakaret onur şeref saygınlık suç": [
            "küfür etti",
            "bana küfür",
            "beni aşağıladı",
            "hakaret etti",
        ],

        "tehdit korkutma zarar verme suç": [
            "beni tehdit etti",
            "öldürürüm dedi",
            "zarar vereceğini söyledi",
            "korkutuyor",
        ],
    }

    additions = []

    for (
        legal_concepts,
        expressions
    ) in concept_map.items():

        if any(
            expression in q
            for expression in expressions
        ):
            additions.append(
                legal_concepts
            )
    if semantic_intents is None:
     semantic_intents = detect_semantic_intents(question)

    print(
        "Semantik niyetler:",
        semantic_intents,
    )

    for intent_name, score in semantic_intents:
        expansion = INTENT_PROTOTYPES[intent_name][1]

        if expansion not in additions:
            additions.append(expansion)

    if additions:
        return question + " " + " ".join(additions)

    return question




# ============================================================
# ONCELIKLI MADDELER
# ============================================================

def preferred_article_keys(
    question,
):
    q = normalize(question)

    preferred = []
    # ACIKCA YAZILAN KANUN + MADDEYI YAKALA
    law_match = re.search(
        r"\b(\d{1,4})\b",
        q,
    )

    article_match = re.search(
        r"\b(?:(ek|geçici|gecici|mükerrer|mukerrer)\s+)?madde\s+(\d+)\b",
        q,
    )

    if law_match and article_match:
        kanun_no = law_match.group(1)
        madde_turu = article_match.group(1)
        madde_no = article_match.group(2)

        if madde_turu == "ek":
            madde = f"EK {madde_no}"
        elif madde_turu in ("geçici", "gecici"):
            madde = f"GEÇİCİ {madde_no}"
        elif madde_turu in ("mükerrer", "mukerrer"):
            madde = f"MÜKERRER {madde_no}"
        else:
            madde = madde_no

        preferred.append(
            (kanun_no, madde)
        )

        # 4857 IS KANUNU

    if "deneme" in q:
        preferred.append(
            ("4857", "15")
        )

    if (
        "maaş" in q
        or "ücretim" in q
        or "ücretimi" in q
        or "maaşım" in q
        or "maaşımı" in q
        or "ücret ödenm" in q
        or "maaş ödenm" in q
    ):
        preferred.extend(
            [
                ("4857", "32"),
                ("4857", "34"),
            ]
        )
    if (
        "kıdem tazminatı" in q
        or "kıdem tazminatımı" in q
        or "kıdem tazminat" in q
    ):
        preferred.append(
            ("1475", "14")
        )

    if (
        "7 gün" in q
        or "yedi gün" in q
        or "hafta tatili" in q
        or "haftalık dinlenme" in q
        or "aralıksız" in q
    ):
        preferred.append(
            ("4857", "46")
        )

    if (
        "yıllık ücretli izin" in q
        or "yıllık izin hakkı" in q
        or "yıllık izin" in q
    ):
        preferred.append(
            ("4857", "53")
        )


    if (
        "haftada 6 gün" in q
        or "6 gün çalış" in q
        or "altı gün çalış" in q
    ):
        preferred.append(
            ("4857", "63")
        )

    # 4721 MEDENI KANUN

    if (
        "yasal mirasçı" in q
        or "yasal mirasçılar" in q
        or "miras kime kalır" in q
        or "miras paylaşımı" in q
        or "sağ kalan eş" in q
    ):
        preferred.extend(
            [
                ("4721", "495"),
                ("4721", "496"),
                ("4721", "497"),
                ("4721", "499"),
            ]
        )


       # 6502 TUKETICI

    if (
        "ayıplı" in q
        or "tüketici" in q
        or (
            "ürün" in q
            and (
                "bozul" in q
                or "bozuk" in q
                or "arızalı" in q
                or "kusurlu" in q
                or "iade" in q
                or "değiştir" in q
            )
        )
        or (
            "telefon" in q
            and (
                "bozul" in q
                or "bozuk" in q
                or "arızalı" in q
                or "kusurlu" in q
            )
        )
    ):
        preferred.extend(
            [
                ("6502", "8"),
                ("6502", "10"),
                ("6502", "11"),
            ]
        )
    # 634 KAT MULKIYETI KANUNU

    if (
        "aidat" in q
        or "apartman gider" in q
        or "ortak gider" in q
        or "gider avansı" in q
        or "gider avansi" in q
    ):
        preferred.extend(
            [
                ("634", "20"),
                ("634", "22"),
            ]
        )
            # 2004 ICRA VE IFLAS KANUNU

    if (
        "icra takibi" in q
        or "ödeme emri" in q
        or "odeme emri" in q
        or "haciz" in q
    ):
        preferred.extend(
            [
                ("2004", "60"),
                ("2004", "62"),
            ]
        )

       # 2644 TAPU KANUNU

    if (
        "tapu" in q
        or "tescil" in q
        or ("taşınmaz" in q and "tescil" in q)
        or ("gayrimenkul" in q and "tescil" in q)
    ):
        preferred.append(
            ("2644", "26")
        )
        # 3194 IMAR KANUNU

    if (
        "ruhsat" in q
        or "ruhsatsız" in q
        or "kaçak yapı" in q
        or "imar" in q
    ):
        preferred.extend(
            [
                ("3194", "21"),
                ("3194", "32"),
                ("3194", "42"),
            ]
        )
                # 5502 SOSYAL GUVENLIK KURUMU KANUNU - SGK GOREVLERI
    if (
        "sosyal güvenlik kurumunun görevleri" in q
        or "sosyal güvenlik kurumu görevleri" in q
        or "sgk'nın görevleri" in q
        or "sgk görevleri" in q
        or (
            "sosyal güvenlik kurumu" in q
            and (
                "görev" in q
                or "yetki" in q
                or "ne iş yapar" in q
                or "ne yapar" in q
            )
        )
    ):
        preferred.append(
            ("4", "405")
        )
    # 5411 BANKACILIK KANUNU - MUSTERI SIRRI

    if (
        "müşteri sırrı" in q
        or "müşteri bilgileri" in q
        or "banka müşterisi" in q
        or (
            "banka" in q
            and (
                "kişisel bilgi" in q
                or "finansal bilgi" in q
                or "bilgilerimi paylaştı" in q
                or "bilgilerimin paylaşılması" in q
                or "başkalarıyla paylaş" in q
            )
        )
    ):
        preferred.append(
            ("5411", "73")
        )

    # 5464 BANKA KARTLARI VE KREDI KARTLARI KANUNU

    if (
        "kredi kartı" in q
        or "kredi karti" in q
        or "banka kartı" in q
        or "banka karti" in q
        or "kartımdan" in q
        or "kartimdan" in q
        or "bilgim dışında" in q
        or "bilgim disinda" in q
        or "iznim dışında" in q
        or "iznim disinda" in q
        or "yetkisiz işlem" in q
        or "yetkisiz islem" in q
    ):
        preferred.extend(
            [
                ("5464", "11"),
                ("5464", "12"),
                ("5464", "15"),
                ("5464", "16"),
                ("5464", "32"),
            ]
        )


    # 6563 ELEKTRONIK TICARET KANUNU

    if (
        "reklam mesajı" in q
        or "reklam mesaji" in q
        or "ticari elektronik ileti" in q
        or "istenmeyen mesaj" in q
        or "sms reklam" in q
    ):
        preferred.extend(
            [
                ("6563", "6"),
                ("6563", "8"),
            ]
        )

    # 5510 SOSYAL SIGORTALAR VE GENEL SAGLIK SIGORTASI KANUNU

    if (
        "iş kazası" in q
        or "iş kazası geçirdim" in q
        or "iş kazası sayılır" in q
    ):
        preferred.append(
            ("5510", "13")
        )

    # 5237 TCK

        # 6284 - KORUYUCU VE ONLEYICI TEDBIRLER

    if (
        "eski eş" in q
        or "eski esim" in q
        or "eski eşim" in q
        or "ısrarlı takip" in q
        or "takip ediyor" in q
        or "koruma kararı" in q
        or "uzaklaştırma" in q
        or "şiddet mağduru" in q
        or "aile içi şiddet" in q
    ):
        preferred.extend([
            ("6284", "1"),
            ("6284", "4"),
            ("6284", "5"),
            ("6284", "8"),
        ])

    # 5237 - TURK CEZA KANUNU

    if (
    "hırsızlık" in q
    or "çalındı" in q
    or "çaldı" in q
    or (
        "telefon" in q
        and (
            "iznim olmadan" in q
            or "rızam olmadan" in q
        )
        and (
            "aldı" in q
            or "alındı" in q
            or "geri vermiyor" in q
        )
    )
):
        preferred.append(
        ("5237", "141")
    )
    if (
        "telefonumu" in q
        or "telefonumu aldı" in q
        or "telefonumu geri vermiyor" in q
        or (
            "iznim olmadan aldı" in q
            and "geri vermiyor" in q
        )
    ):
        preferred.append(
            ("5237", "141")
        )

    if "dolandırıcılık" in q:
        preferred.append(
            ("5237", "157")
        )

    if "hakaret" in q:
        preferred.append(
            ("5237", "125")
        )

    if "tehdit" in q:
        preferred.append(
            ("5237", "106")
        )

    unique = []
    seen = set()

    for item in preferred:
        if item in seen:
            continue

        seen.add(item)
        unique.append(item)

    return unique


def get_preferred_articles(
    question,
    candidates,
    semantic_intents=None,
):
    keys = preferred_article_keys(question)

    if semantic_intents:
        for name, _score in semantic_intents:
            keys.extend(
          INTENT_PREFERRED_ARTICLES.get(name, [])
            )

    preferred = []
    for law_number, article_number_value in keys:
        direct_item = DIRECT_ARTICLES.get(
            (law_number, article_number_value)
        )

        if direct_item is not None:
            preferred.append(
                direct_item.copy()
            )

    for law_number, article_number_value in keys:
        for candidate in candidates:
            if (
                get_law_number(candidate["kanun"]) == law_number
                and str(candidate["madde"]) == article_number_value
            ):
                item = candidate.copy()
                item["oncelikli"] = True
                item["score"] = 999999
                preferred.append(item)
                break

    return unique_results(preferred)


# ============================================================
# RETRIEVAL
# ============================================================
INTENT_PREFERRED_ARTICLES = {
    "miras_mirascilar": [
        ("4721", "495"),
        ("4721", "496"),
        ("4721", "497"),
        ("4721", "499"),
    ],

    "miras_es_payi": [
        ("4721", "499"),
    ],

    "miras_sakli_pay": [
        ("4721", "506"),
    ],
        "kira_artisi": [
        ("6098", "344"),
    ],
        "kira": [
        ("6098", "352"),
    ],

    "ihbar_suresi": [
        ("4857", "17"),
    ],
        "isci_hakli_fesih": [
        ("4857", "24"),
    ],

    "isveren_hakli_fesih": [
        ("4857", "25"),
    ],

    "kisisel_veri_haklari": [
        ("6698", "11"),
    ],
    "kisisel_veri_aktarim": [
    ("6698", "8"),
],
}
def get_intent_law_numbers(semantic_intents):
    law_numbers = set()

    for name, _score in semantic_intents:
        expansion = INTENT_PROTOTYPES[name][1]

        numbers = re.findall(
            r"\b\d{1,4}\b",
            expansion,
        )

        law_numbers.update(numbers)

    return law_numbers
def retrieve(question):
    semantic_intents = detect_semantic_intents(question)
    expanded_question = expand_query(
    question,
    semantic_intents
)
    intent_law_numbers = get_intent_law_numbers(
        semantic_intents
    )

    print(
        "Orijinal soru:",
        question,
    )

    print(
        "Genisletilmis sorgu:",
        expanded_question,
    )

    embedding = model.encode(
        expanded_question
    ).tolist()

    result = collection.query(
        query_embeddings=[
            embedding
        ],
        n_results=min(
            30,
            collection.count(),
        ),
        include=[
            "metadatas",
            "documents",
            "distances",
        ],
    )

    documents = result[
        "documents"
    ][0]

    metadatas = result[
        "metadatas"
    ][0]

    distances = result[
        "distances"
    ][0]

    candidates = []

    for (
        document,
        metadata,
        distance,
    ) in zip(
        documents,
        metadatas,
        distances,
    ):
        law = clean_law_name(
            metadata.get(
                "kanun",
                "",
            )
        )

        law_number = get_law_number(
            law
        )

        article = article_number(
            metadata,
            document,
        )

        semantic_score = (
            1
            / (
                1
                + float(
                    distance
                )
            )
        )
        

        law_score = 0

        if law_number in intent_law_numbers:
            law_score = 2

        score = (
            semantic_score * 10
            + keyword_score(question, document) * 4
            + concept_score(question, document)
            + title_score(question, document) * 3
            + law_score
        )
        

        candidates.append(
            {
                "kanun": law,
                "kanun_no": law_number,
                "madde": article,
                "icerik": document,
                "mesafe": float(
                    distance
                ),
                "skor": score,
                "oncelikli": False,
            }
        )
        
    candidates.sort(
        key=lambda item: item[
            "skor"
        ],
        reverse=True,
    )

    preferred = (
    get_preferred_articles(
        question,
        candidates,
        semantic_intents,
    )
)

    print(
        "Oncelikli maddeler:",
        [
            (
                f"{item['kanun_no']} "
                f"Madde {item['madde']}"
            )
            for item in preferred
        ],
    )

    combined = []

    combined.extend(
        preferred
    )

    for candidate in candidates:
        candidate_key = article_key(
            candidate
        )

        already_exists = any(
            article_key(item)
            == candidate_key
            for item in combined
        )

        if already_exists:
            continue

        combined.append(
            candidate
        )
        combined = unique_results(
        combined
    )

    print("Ilk 8 retrieval sonucu:")

    for i, item in enumerate(
        combined[:8],
        start=1,
    ):
        print(
            i,
            item["kanun"],
            "Madde",
            item["madde"],
            "SKOR:",
            round(item["skor"], 2),
            "ONCELIKLI:",
            item["oncelikli"],
        )

    return combined[:8]


# ============================================================
# GEMINI CONTEXT
# ============================================================

def build_context(results):
    parts = []

    for index, item in enumerate(
        results,
        start=1,
    ):
        oncelik = (
            "EVET"
            if item.get("oncelikli")
            else "HAYIR"
        )

        parts.append(
            f"KAYNAK {index}\n\n"
            f"ONCELIKLI KAYNAK:\n"
            f"{oncelik}\n\n"
            f"KANUN NUMARASI:\n"
            f"{item['kanun_no']}\n\n"
            f"KANUN:\n"
            f"{item['kanun']}\n\n"
            f"MADDE:\n"
            f"{item['madde']}\n\n"
            f"MADDE METNI:\n"
            f"{item['icerik']}"
        )

    separator = (
        "\n"
        + "=" * 70
        + "\n\n"
    )

    return (
        "\n\n"
        + separator.join(
            parts
        )
    )


# ============================================================
# AKILLI KAYNAK SECIMI
# ============================================================

def select_used_sources(
    results,
    used_sources,
):
    selected = []
    seen = set()

    available = {
        article_key(item): item
        for item in results
    }

    for source in used_sources:
        if not isinstance(
            source,
            dict,
        ):
            continue

        key = (
            str(
                source.get(
                    "kanun",
                    "",
                )
            ).strip(),
            str(
                source.get(
                    "madde",
                    "",
                )
            ).strip(),
        )

        if key in seen:
            continue

        if key not in available:
            # Gemini'nin kendisine verilmeyen
            # bir maddeyi kaynak göstermesine izin verme.
            continue

        seen.add(key)

        selected.append(
            available[key]
        )

    # Gemini kaynak listesi döndüremediyse
    # kullanıcıyı kaynaksız bırakmamak için
    # yalnızca en güçlü ilk sonucu kullan.
    if not selected and results:
        selected = [
            results[0]
        ]

    return selected[:4]


# ============================================================
# CEVAP URETME
# ============================================================

def cevap_uret(question):
    question = question.strip()

    if not question:
        return {
            "cevap": (
                "Lütfen bir hukuk "
                "sorusu yazın."
            ),
            "kaynaklar": [],
        }

    retrieval_start = time.perf_counter()

    results = retrieve(
        question
    )

    retrieval_time = time.perf_counter() - retrieval_start

    print(
        f"RETRIEVAL SURESI: {retrieval_time:.2f} saniye"
    )

    if not results:
        return {
            "cevap": (
                "Sorunuzla ilgili "
                "mevzuat kaynağı "
                "bulunamadı."
            ),
            "kaynaklar": [],
        }

    context = build_context(
        results
    )

    try:
        llm_result = hukuk_cevapla(
            question,
            context,
        )

        answer = llm_result.get(
            "cevap",
            "",
        )

        used_sources = llm_result.get(
            "kullanilan_kaynaklar",
            [],
        )

    except Exception as error:
        print(
            "Gemini hatasi:",
            error,
        )

        answer = (
            "Gemini cevap uretemedi. "
            "Lutfen tekrar deneyin."
        )

        used_sources = []

    selected = select_used_sources(
        results,
        used_sources,
    )

    sources = [
        {
            "kanun": item[
                "kanun"
            ],
            "madde": item[
                "madde"
            ],
            "icerik": item[
                "icerik"
            ],
        }
        for item in selected
    ]

    print(
        "Gemini'nin kullandigi kaynaklar:",
        used_sources,
    )

    print(
        "Kullaniciya gosterilen kaynaklar:",
        [
            (
                f"{item['kanun']} "
                f"Madde {item['madde']}"
            )
            for item in sources
        ],
    )

    return {
        "cevap": answer,
        "kaynaklar": sources,
    }


# ============================================================
# API
# ============================================================

@app.get("/")
def root():
    return {
        "mesaj": (
            "HukukAI calisiyor."
        ),
        "durum": (
            "RAG + Semantik Niyet + Gemini + "
            "Akilli Kaynak Secimi aktif"
        ),
        "versiyon": "1.8.0",
        "chroma_kayit": (
            collection.count()
        ),
    }


@app.post("/sor")
def sor(soru: Soru):
    return cevap_uret(
        soru.soru
    )
# ============================================================
# MEVZUAT ARAMA
# ============================================================

@app.get("/mevzuat-ara")
def mevzuat_ara(q: str):
    sorgu = q.strip()

    if not sorgu:
        return {"sonuclar": []}

    sorgu_normal = normalize(sorgu)
    sonuclar = []

    # 4857 Madde 46 gibi doğrudan aramaları yakala
    law_match = re.search(
        r"\b(\d{3,4})\b",
        sorgu_normal,
    )

    article_match = re.search(
        r"\b(?:(ek|geçici|gecici|mükerrer|mukerrer)\s+)?madde\s+(\d+)\b",
        sorgu_normal,
    )

    if law_match and article_match:
        kanun_no = law_match.group(1)
        madde_turu = article_match.group(1)
        madde_no = article_match.group(2)

        if madde_turu == "ek":
            madde = f"EK {madde_no}"
        elif madde_turu in ("geçici", "gecici"):
            madde = f"GEÇİCİ {madde_no}"
        elif madde_turu in ("mükerrer", "mukerrer"):
            madde = f"MÜKERRER {madde_no}"
        else:
            madde = madde_no

        key = (kanun_no, madde)

        if key in DIRECT_ARTICLES:
            item = DIRECT_ARTICLES[key]

            return {
                "sorgu": sorgu,
                "sonuclar": [
                    {
                        "kanun": item["kanun"],
                        "kanun_no": item["kanun_no"],
                        "madde": item["madde"],
                        "icerik": item["icerik"],
                    }
                ],
            }

    # Sadece kanun numarası yazılmışsa o kanunun maddelerini getir
    if re.fullmatch(r"\d{3,4}", sorgu_normal):
        for (kanun_no, madde_no), item in DIRECT_ARTICLES.items():
            if kanun_no == sorgu_normal:
                sonuclar.append(
                    {
                        "kanun": item["kanun"],
                        "kanun_no": kanun_no,
                        "madde": item["madde"],
                        "icerik": item["icerik"],
                    }
                )

            if len(sonuclar) >= 20:
                break

        return {
            "sorgu": sorgu,
            "sonuclar": sonuclar,
        }

    # Diğer sorgular için semantik arama
    embedding = model.encode(sorgu).tolist()

    result = collection.query(
        query_embeddings=[embedding],
        n_results=10,
        include=[
            "metadatas",
            "documents",
            "distances",
        ],
    )
    

    for document, metadata in zip(
        result["documents"][0],
        result["metadatas"][0],
    ):
        if str(metadata.get("madde_turu") or "NORMAL MADDE").upper() != "NORMAL MADDE":

         continue
        
        document = html.unescape(document or "")
        kanun = clean_law_name(
            metadata.get("kanun", "")
        )

        sonuclar.append(
            {
                "kanun": kanun,
                "kanun_no": get_law_number(kanun),
                "madde": article_number(
                    metadata,
                    document,
                ),
                "icerik": document,
            }
        )

    return {
        "sorgu": sorgu,
        "sonuclar": sonuclar,
    }
# ============================================================
# DILEKCE / BASVURU TASLAGI
# ============================================================

@app.post("/dilekce-olustur")
def dilekce_endpoint(istek: DilekceIstegi):
    soru = istek.soru.strip()
    cevap = istek.cevap.strip()

    if not soru:
        return {
            "baslik": "Başvuru Taslağı",
            "dilekce": "Dilekçe oluşturmak için olay bilgisi bulunamadı.",
            "kaynaklar": [],
        }

    # Kullanıcının olayına uygun mevzuatı tekrar bul.
    results = retrieve(soru)

    if not results:
        return {
            "baslik": "Başvuru Taslağı",
            "dilekce": (
                "Bu olay için yeterli mevzuat kaynağı "
                "bulunamadığından güvenilir bir taslak oluşturulamadı."
            ),
            "kaynaklar": [],
        }

    # Bulunan mevzuatı Gemini'ye verilecek bağlama dönüştür.
    context = build_context(results)

    try:
        sonuc = dilekce_olustur(
            soru,
            cevap,
            context,
        )

        baslik = str(
            sonuc.get(
                "baslik",
                "Başvuru Taslağı",
            )
        ).strip()

        dilekce = str(
            sonuc.get(
                "dilekce",
                "",
            )
        ).strip()

    except Exception as error:
        print(
            "Dilekce olusturma hatasi:",
            error,
        )

        return {
            "baslik": "Başvuru Taslağı",
            "dilekce": (
                "Dilekçe oluşturulurken bir hata oluştu. "
                "Lütfen tekrar deneyin."
            ),
            "kaynaklar": [],
        }

       # Gemini'nin dilekçede gerçekten kullandığı kaynakları al.
    used_sources = sonuc.get(
        "kullanilan_kaynaklar",
        [],
    )

    print(
        "Dilekcede Gemini'nin kullandigi kaynaklar:",
        used_sources,
    )

    # Sadece gerçekten kullanılan maddeleri seç.
    selected = select_used_sources(
        results,
        used_sources,
    )

    kaynaklar = [
        {
            "kanun": item["kanun"],
            "madde": item["madde"],
            "icerik": item["icerik"],
        }
        for item in selected
    ]

    print(
        "Dilekcede kullaniciya gosterilen kaynaklar:",
        [
            f"{item['kanun']} Madde {item['madde']}"
            for item in kaynaklar
        ],
    )

    return {
        "baslik": baslik or "Başvuru Taslağı",
        "dilekce": dilekce,
        "kaynaklar": kaynaklar,
    }

# ============================================================
# DILEKCE WORD / PDF INDIRME
# ============================================================

def guvenli_dosya_adi(baslik: str, uzanti: str) -> str:
    ad = re.sub(r'[^a-zA-Z0-9çğıöşüÇĞİÖŞÜ _-]+', '', baslik or 'dilekce').strip()
    ad = re.sub(r'\s+', '_', ad)
    if not ad:
        ad = 'dilekce'
    return f"{ad[:80]}.{uzanti}"


@app.post("/dilekce-word")
def dilekce_word(istek: DilekceDosyaIstegi):
    baslik = istek.baslik.strip() or "Başvuru Taslağı"
    metin = istek.dilekce.strip()

    if not metin:
        return {"hata": "Word oluşturmak için dilekçe metni bulunamadı."}

    document = Document()

    normal_style = document.styles["Normal"]
    normal_style.font.name = "Arial"
    normal_style.font.size = Pt(11)

    title = document.add_heading(baslik, level=1)
    title.alignment = 1

    for satir in metin.splitlines():
        satir = satir.rstrip()
        if not satir:
            document.add_paragraph("")
            continue

        p = document.add_paragraph()
        run = p.add_run(satir)

        # Dilekçedeki bölüm başlıklarını belirginleştir.
        if satir.strip().upper().rstrip(":") in {
            "BAŞVURAN", "KONU", "AÇIKLAMALAR", "HUKUKİ DAYANAK",
            "TALEP", "TARİH", "AD SOYAD", "İMZA"
        }:
            run.bold = True

    buffer = io.BytesIO()
    document.save(buffer)
    buffer.seek(0)

    dosya_adi = guvenli_dosya_adi(baslik, "docx")

    return StreamingResponse(
        buffer,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={
    "Content-Disposition": 'attachment; filename="dilekce_taslagi.docx"'
},
    )


def pdf_font_hazirla():
    """Windows'ta Türkçe karakterleri destekleyen bir font bulur."""
    adaylar = [
        ("Arial", r"C:\\Windows\\Fonts\\arial.ttf"),
        ("Calibri", r"C:\\Windows\\Fonts\\calibri.ttf"),
        ("DejaVuSans", r"C:\\Windows\\Fonts\\DejaVuSans.ttf"),
    ]

    for font_adi, font_yolu in adaylar:
        if os.path.exists(font_yolu):
            if font_adi not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(font_adi, font_yolu))
            return font_adi

    return "Helvetica"


@app.post("/dilekce-pdf")
def dilekce_pdf(istek: DilekceDosyaIstegi):
    baslik = istek.baslik.strip() or "Başvuru Taslağı"
    metin = istek.dilekce.strip()

    if not metin:
        return {"hata": "PDF oluşturmak için dilekçe metni bulunamadı."}

    buffer = io.BytesIO()
    font_adi = pdf_font_hazirla()

    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=50,
        leftMargin=50,
        topMargin=50,
        bottomMargin=50,
        title=baslik,
    )

    styles = getSampleStyleSheet()

    baslik_style = ParagraphStyle(
        "HukukAIBaslik",
        parent=styles["Title"],
        fontName=font_adi,
        fontSize=15,
        leading=19,
        spaceAfter=18,
    )

    metin_style = ParagraphStyle(
        "HukukAIMetin",
        parent=styles["BodyText"],
        fontName=font_adi,
        fontSize=10.5,
        leading=15,
        spaceAfter=6,
    )

    story = [
        Paragraph(
            html.escape(baslik),
            baslik_style
        ),
        Spacer(1, 8)
    ]

    for satir in metin.splitlines():
        satir = satir.rstrip()

        if not satir:
            story.append(Spacer(1, 8))
            continue

        guvenli = html.escape(satir)

        if satir.strip().upper().rstrip(":") in {
            "BAŞVURAN",
            "KONU",
            "AÇIKLAMALAR",
            "HUKUKİ DAYANAK",
            "TALEP",
            "TARİH",
            "AD SOYAD",
            "İMZA"
        }:
            guvenli = f"<b>{guvenli}</b>"

        story.append(
            Paragraph(
                guvenli,
                metin_style
            )
        )

    pdf.build(story)

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                'attachment; filename="dilekce_taslagi.pdf"'
        },
    )