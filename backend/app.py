from pdf_reader import tum_pdfleri_oku
from text_processor import maddelere_ayir
from dataset_builder import veri_seti_olustur, json_kaydet

veriler = tum_pdfleri_oku("../dataset")

tum_maddeler = {}

for dosya, metin in veriler.items():
    tum_maddeler[dosya] = maddelere_ayir(metin)

dataset = veri_seti_olustur(tum_maddeler)

json_kaydet(dataset)

print("✅ hukuk_dataset.json oluşturuldu.")
print("Toplam kayıt:", len(dataset))