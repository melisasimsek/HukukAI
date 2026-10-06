import re


def maddelere_ayir(metin):
    """
    Kanun metnindeki maddeleri ayırır.
    Maddenin üstündeki başlığı ilgili maddeye ekler.
    Sonraki maddenin başlığının önceki maddeye karışmasını engeller.
    """

    if not metin:
        return []

    satirlar = metin.splitlines()

    madde_deseni = re.compile(
        r'^(?:(?:GEÇİCİ|EK|MÜKERRER)\s+)?MADDE\s+\d+\s*(?:[-–—]|$)',
        re.IGNORECASE
    )

    madde_baslangiclari = []

    # MADDE satırlarının konumlarını bul
    for i, satir in enumerate(satirlar):
        if madde_deseni.match(satir.strip()):
            madde_baslangiclari.append(i)

    maddeler = []

    for index, madde_satiri in enumerate(madde_baslangiclari):

        # Varsayılan başlangıç MADDE satırıdır.
        baslangic = madde_satiri

        # Maddenin üstündeki boş satırları geç.
        j = madde_satiri - 1

        while j >= 0 and not satirlar[j].strip():
            j -= 1

        # İlk boş olmayan satırı başlık olarak al.
        if j >= 0:
            baslangic = j

        # Sonraki madde varsa onun başlığından önce bitir.
        if index + 1 < len(madde_baslangiclari):
            sonraki_madde = madde_baslangiclari[index + 1]

            j = sonraki_madde - 1

            # Sonraki MADDE'nin üstündeki boş satırları geç.
            while j >= 0 and not satirlar[j].strip():
                j -= 1

            # Bulduğumuz satır sonraki maddenin başlığıdır.
            bitis = j

        else:
            bitis = len(satirlar)

        parca = "\n".join(
            satirlar[baslangic:bitis]
        ).strip()

        if parca:
            maddeler.append(parca)

    return maddeler