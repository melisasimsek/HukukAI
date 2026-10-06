import fitz
import json
import re
from pathlib import Path


KLASOR = Path(__file__).parent
CIKTI = KLASOR / "yeni_mevzuat_dataset.json"

ESKI_KANUNLAR = {
    "2709", "4721", "4857", "5237", "5271",
    "5510", "6098", "6100", "6502", "6698"
}


def kanun_no_bul(dosya_adi):
    match = re.match(r"\s*(\d+)", dosya_adi)
    return match.group(1) if match else None


def pdf_metni_oku(pdf_yolu):
    parcalar = []

    with fitz.open(pdf_yolu) as pdf:
        for sayfa in pdf:
            metin = sayfa.get_text("text")

            if metin:
                parcalar.append(metin)

    return "\n".join(parcalar)


def temizle(metin):
    metin = metin.replace("\u00ad", "")
    metin = metin.replace("\xa0", " ")
    metin = metin.replace("\r", "\n")

    satirlar = [
        satir.rstrip()
        for satir in metin.splitlines()
    ]

    metin = "\n".join(satirlar)

    metin = re.sub(
        r"\n{3,}",
        "\n\n",
        metin
    )

    return metin.strip()


def ek_tablolari_kes(metin):
    """
    Kanunun ana metninden sonra gelen değişiklik,
    yürürlük ve Resmi Gazete tablolarını keser.
    """

    kesme_ifadeleri = [
        r"DEĞİŞİKLİK YAPAN MEVZUATIN",
        r"Değişiklik Yapan Mevzuatın",
        r"DEĞİŞİKLİK YAPAN KANUNUN",
        r"Değişiklik Yapan Kanunun",
        r"DEĞİŞTİREN KANUNUN",
        r"Değiştiren Kanunun",
        r"DEĞİŞTİREN\s+KANUNUN[/\s]*KHK",
        r"Değiştiren\s+Kanunun[/\s]*KHK",
        r"DEĞİŞTİREN\s+KANUNUN[/\s]*KHK.?NİN NUMARASI",
        r"Değiştiren\s+Kanunun[/\s]*KHK.?nin Numarası",
        r"YÜRÜRLÜKTEN KALDIRAN MEVZUATIN",
        r"Yürürlükten Kaldıran Mevzuatın",
        r"KANUNA İŞLENEMEYEN",
        r"Kanuna İşlenemeyen",
        r"KANUNDA YAPILAN DEĞİŞİKLİKLER",
        r"Kanunda Yapılan Değişiklikler",
    ]

    bulunanlar = []

    for ifade in kesme_ifadeleri:
        match = re.search(
            ifade,
            metin,
            flags=re.IGNORECASE
        )

        if match:
            bulunanlar.append(
                match.start()
            )

    if bulunanlar:
        return metin[:min(bulunanlar)]

    return metin


def tablo_kaydi_mi(icerik):
    """
    Yanlışlıkla madde gibi yakalanan değişiklik
    ve yürürlük tablolarını tespit eder.
    """

    ilk_1000 = icerik[:1000].lower()

    supheli_ifadeler = [
        "değiştiren kanunun",
        "değiştiren kanun",
        "değişen veya iptal edilen maddeleri",
        "yürürlüğe giriş tarihi",
        "değişiklik yapan mevzuat",
        "değişiklik yapan kanun",
        "yayımlandığı resmî gazetenin",
        "yayımlandığı resmi gazetenin",
        "kanunun/khk",
        "kanunun / khk",
    ]

    eslesme_sayisi = sum(
        ifade in ilk_1000
        for ifade in supheli_ifadeler
    )

    return eslesme_sayisi >= 2


def madde_anahtari(tur, numara):
    """
    Aynı kanun içindeki madde türlerini birbirinden ayırır.

    Örnek:
    MADDE 5
    EK MADDE 5
    GEÇİCİ MADDE 5

    birbirinden farklı kayıtlar olarak tutulur.
    """

    return (
        tur.upper().strip(),
        str(numara).strip()
    )


def maddeleri_ayir(metin):
    """
    Normal MADDE yanında:

    - EK MADDE
    - GEÇİCİ MADDE
    - MÜKERRER MADDE

    kayıtlarını da yakalar.
    """

    desen = re.compile(
        r"(?im)^[ \t]*"
        r"(?:(EK|GEÇİCİ|GECICI|MÜKERRER|MUKERRER)[ \t]+)?"
        r"MADDE[ \t]+"
        r"(\d+)"
        r"(?:[ \t]*[/-][ \t]*(?:[A-ZÇĞİÖŞÜa-zçğıöşü]|\d+))?"
        r"[ \t]*(?:[-–—])?"
    )

    eslesmeler = list(
        desen.finditer(metin)
    )

    maddeler = []
    gorulen_maddeler = set()

    for i, eslesme in enumerate(eslesmeler):

        tur_raw = eslesme.group(1)
        numara = eslesme.group(2)

        if tur_raw:
            tur_raw = tur_raw.upper()

        if tur_raw in ("GEÇİCİ", "GECICI"):
            madde_turu = "GEÇİCİ MADDE"

        elif tur_raw in ("MÜKERRER", "MUKERRER"):
            madde_turu = "MÜKERRER MADDE"

        elif tur_raw == "EK":
            madde_turu = "EK MADDE"

        else:
            madde_turu = "MADDE"

        baslangic = eslesme.start()

        if i + 1 < len(eslesmeler):
            bitis = eslesmeler[i + 1].start()
        else:
            bitis = len(metin)

        icerik = temizle(
            metin[baslangic:bitis]
        )

        if not icerik:
            continue

        if len(icerik) < 40:
            continue

        if tablo_kaydi_mi(icerik):
            continue

        anahtar = madde_anahtari(
            madde_turu,
            numara
        )

        if anahtar in gorulen_maddeler:
            continue

        gorulen_maddeler.add(
            anahtar
        )

        # Normal maddelerde eski veri yapısını koruyoruz.
        # Özel maddelerde benzersiz madde_no oluşturuyoruz.
        if madde_turu == "MADDE":
            madde_no = int(numara)

        elif madde_turu == "EK MADDE":
            madde_no = f"EK {numara}"

        elif madde_turu == "GEÇİCİ MADDE":
            madde_no = f"GEÇİCİ {numara}"

        else:
            madde_no = f"MÜKERRER {numara}"

        maddeler.append({
            "madde_no": madde_no,
            "madde_turu": madde_turu,
            "icerik": icerik
        })

    return maddeler


tum_kayitlar = []
rapor = []

pdfler = sorted(
    KLASOR.glob("*.pdf"),
    key=lambda p: p.name.lower()
)

print(
    f"Toplam PDF: {len(pdfler)}"
)

print("-" * 60)


for pdf_yolu in pdfler:

    kanun_no = kanun_no_bul(
        pdf_yolu.name
    )

    if not kanun_no:
        print(
            f"ATLANDI: {pdf_yolu.name}"
        )
        continue

    if kanun_no in ESKI_KANUNLAR:
        print(
            f"MEVCUT DATASET - ATLANDI: "
            f"{pdf_yolu.name}"
        )
        continue

    try:

        metin = pdf_metni_oku(
            pdf_yolu
        )

        metin = temizle(
            metin
        )

        metin = ek_tablolari_kes(
            metin
        )

        maddeler = maddeleri_ayir(
            metin
        )

        normal_sayi = 0
        ek_sayi = 0
        gecici_sayi = 0
        mukerrer_sayi = 0

        for madde in maddeler:

            tur = madde["madde_turu"]

            if tur == "MADDE":
                normal_sayi += 1

            elif tur == "EK MADDE":
                ek_sayi += 1

            elif tur == "GEÇİCİ MADDE":
                gecici_sayi += 1

            elif tur == "MÜKERRER MADDE":
                mukerrer_sayi += 1

            tum_kayitlar.append({
                "kanun": pdf_yolu.name,
                "madde_no": madde["madde_no"],
                "madde_turu": madde["madde_turu"],
                "icerik": madde["icerik"]
            })

        rapor.append({
            "kanun": pdf_yolu.name,
            "madde_sayisi": len(maddeler),
            "normal": normal_sayi,
            "ek": ek_sayi,
            "gecici": gecici_sayi,
            "mukerrer": mukerrer_sayi
        })

        print(
            f"OK: {pdf_yolu.name} -> "
            f"{len(maddeler)} kayıt "
            f"(Normal:{normal_sayi} "
            f"Ek:{ek_sayi} "
            f"Geçici:{gecici_sayi} "
            f"Mükerrer:{mukerrer_sayi})"
        )

    except Exception as hata:

        print(
            f"HATA: {pdf_yolu.name} -> "
            f"{hata}"
        )


with open(
    CIKTI,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        tum_kayitlar,
        f,
        ensure_ascii=False,
        indent=2
    )


print("-" * 60)

print(
    f"Yeni toplam kayit: "
    f"{len(tum_kayitlar)}"
)

print(
    f"Dosya olusturuldu: "
    f"{CIKTI.name}"
)

print("\nKANUN RAPORU")
print("-" * 60)

for item in rapor:

    print(
        f"{item['madde_sayisi']:>4} | "
        f"N:{item['normal']:>4} "
        f"E:{item['ek']:>3} "
        f"G:{item['gecici']:>3} "
        f"M:{item['mukerrer']:>3} | "
        f"{item['kanun']}"
    )