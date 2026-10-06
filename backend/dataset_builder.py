import json
import re
import html


def metni_temizle(metin):
    if not metin:
        return ""

    metin = str(metin)

    for _ in range(5):
        yeni_metin = html.unescape(metin)

        if yeni_metin == metin:
            break

        metin = yeni_metin

    metin = metin.replace("&#x20;", " ")
    metin = metin.replace("&#X20;", " ")
    metin = metin.replace("&#32;", " ")
    metin = metin.replace("&nbsp;", " ")
    metin = metin.replace("\xa0", " ")

    return metin


def veri_seti_olustur(veriler):
    dataset = []

    for kanun, maddeler in veriler.items():

        for madde in maddeler:
            if not isinstance(madde, str):
                continue

            madde = metni_temizle(madde).strip()

            if not madde:
                continue

            # MADDE artık ilk satırda olmak zorunda değil.
            # Önünde madde başlığı bulunabilir.
            eslesme = re.search(
                r"(?m)^(?:(GEÇİCİ|EK|MÜKERRER)\s+)?MADDE\s+(\d+)\s*(?:[-–—]|$)",
                madde,
                flags=re.IGNORECASE
            )

            if not eslesme:
                continue

            tur = (eslesme.group(1) or "").upper()

            if tur == "GEÇİCİ":
                madde_turu = "GEÇİCİ MADDE"

            elif tur == "EK":
                madde_turu = "EK MADDE"

            elif tur == "MÜKERRER":
                madde_turu = "MÜKERRER MADDE"

            else:
                madde_turu = "NORMAL MADDE"

            madde_no = int(eslesme.group(2))

            dataset.append({
                "kanun": kanun,
                "madde_no": madde_no,
                "madde_turu": madde_turu,
                "icerik": madde
            })

    return dataset


def json_kaydet(dataset):
    with open(
        "../dataset/hukuk_dataset.json",
        "w",
        encoding="utf-8"
    ) as dosya:

        json.dump(
            dataset,
            dosya,
            ensure_ascii=False,
            indent=4
        )