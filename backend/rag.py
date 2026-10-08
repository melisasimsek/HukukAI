# rag.py
from llm import soruyu_optimize_et, hukuk_cevapla
# Arama yaptığın fonksiyonu import et (örn: search.py veya vector_db.py içinden):
from search import search_documents  # kendi fonksiyon adınla değiştir

def rag_pipeline(user_query: str):
    # 1. Adım: Kullanıcının sorusunu hukuki arama sorgusuna dönüştür
    arama_sorgusu = soruyu_optimize_et(user_query)
    
    # 2. Adım: Vektör tabanında optimize edilmiş sorgu ile ara
    ilgili_maddeler = search_documents(arama_sorgusu)
    
    # 3. Adım: Cevap üretirken ORİJİNAL soruyu ve bulunan maddeleri ver
    cevap = hukuk_cevapla(soru=user_query, belgeler=ilgili_maddeler)
    
    return cevap