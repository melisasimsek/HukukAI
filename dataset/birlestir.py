
import json
from pathlib import Path

klasor = Path(__file__).resolve().parent

with open(klasor / "hukuk_dataset.json", "r", encoding="utf-8") as f:
    eski = json.load(f)

with open(klasor / "yeni_mevzuat_dataset.json", "r", encoding="utf-8") as f:
    yeni = json.load(f)

# Madde türlerini standartlaştır
for madde in yeni:
    if madde["madde_turu"] == "MADDE":
        madde["madde_turu"] = "NORMAL MADDE"

# Aynı kanunun iki veri setinde bulunup bulunmadığını kontrol et
eski_kanunlar = {m["kanun"] for m in eski}
yeni_kanunlar = {m["kanun"] for m in yeni}
ortak = eski_kanunlar & yeni_kanunlar

if ortak:
    print("UYARI: Ortak kanunlar bulundu:", ortak)
    print("Birleştirme yapılmadı.")
else:
    birlesik = eski + yeni

    hedef = klasor / "hukuk_dataset_birlesik.json"
    with open(hedef, "w", encoding="utf-8") as f:
        json.dump(birlesik, f, ensure_ascii=False, indent=2)

    print("Eski kayıt:", len(eski))
    print("Yeni kayıt:", len(yeni))
    print("Toplam kayıt:", len(birlesik))
    print("Toplam kanun:", len(eski_kanunlar | yeni_kanunlar))
    print("Birleştirilmiş dosya oluşturuldu!")
