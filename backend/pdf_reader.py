import fitz
import os


def tum_pdfleri_oku(klasor):
    veriler = {}

    if not os.path.exists(klasor):
        print(f"HATA: Klasör bulunamadı: {klasor}")
        return veriler

    pdf_dosyalari = [
        dosya
        for dosya in os.listdir(klasor)
        if dosya.lower().endswith(".pdf")
    ]

    print("=" * 60)
    print(f"PDF SAYISI: {len(pdf_dosyalari)}")
    print("=" * 60)

    for dosya in pdf_dosyalari:
        yol = os.path.join(klasor, dosya)

        print()
        print(f"OKUNUYOR: {dosya}")

        try:
            pdf = fitz.open(yol)

            sayfa_sayisi = len(pdf)
            metin = ""

            for sayfa_no, sayfa in enumerate(pdf, start=1):
                try:
                    sayfa_metni = sayfa.get_text()

                    if sayfa_metni:
                        metin += sayfa_metni + "\n"

                except Exception as hata:
                    print(
                        f"UYARI: {dosya} - "
                        f"{sayfa_no}. sayfa okunamadı: {hata}"
                    )

            pdf.close()

            if not metin.strip():
                print(
                    f"UYARI: {dosya} okunuyor fakat "
                    "metin bulunamadı."
                )
                continue

            veriler[dosya] = metin

            print("OK:", dosya)
            print("Sayfa sayısı:", sayfa_sayisi)
            print("Karakter sayısı:", len(metin))

        except Exception as hata:
            print()
            print("HATA:", dosya)
            print("Hata:", hata)
            print("Bu PDF dataset'e eklenmedi.")

    print()
    print("=" * 60)
    print(f"BAŞARIYLA OKUNAN PDF: {len(veriler)}")
    print("=" * 60)

    return veriler