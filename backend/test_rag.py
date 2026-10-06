import requests

URL = "http://127.0.0.1:8000/sor"

TESTLER = [
    {
        "soru": "İşveren haftalardır beni boş gün vermeden çalıştırıyor, bu yasal mı?",
        "kanun": "4857",
        "maddeler": ["46"],
    },
    {
        "soru": "Mağazadan aldığım ürün ilk gün bozuldu. Ne yapabilirim?",
        "kanun": "6502",
        "maddeler": ["8", "10", "11"],
    },
    {
        "soru": "Annem vefat etti, geride babam, ben ve kardeşim kaldık. Miras nasıl paylaşılır?",
        "kanun": "4721",
        "maddeler": ["495", "499"],
    },
    {
        "soru": "Apartman aidatını ödemezsem ne olur?",
        "kanun": "634",
        "maddeler": ["20", "22"],
    },
    {
        "soru": "Trafik kazasına karıştım. Sürücü olarak yükümlülüklerim nelerdir?",
        "kanun": "2918",
        "maddeler": [],
    },
    {
        "soru": "Borcum nedeniyle hakkımda icra takibi başlatıldı. Ödeme emri gelirse ne olur?",
        "kanun": "2004",
        "maddeler": [],
    },
    {
        "soru": "Devlet memuruna disiplin cezası hangi durumlarda verilebilir?",
        "kanun": "657",
        "maddeler": [],
    },
    {
        "soru": "Bir taşınmazın tapuya tescili ile ilgili kurallar nelerdir?",
        "kanun": "2644",
        "maddeler": [],
    },
    {
        "soru": "Ruhsatsız bir yapı yaptırırsam ne olur?",
        "kanun": "3194",
        "maddeler": [],
    },
    {
        "soru": "Devlet arazimi kamulaştırmak isterse bedel nasıl belirlenir?",
        "kanun": "2942",
        "maddeler": [],
    },
    {
        "soru": "Türkiye'de yaşayan bir yabancı ikamet izni almak zorunda mı?",
        "kanun": "6458",
        "maddeler": [],
    },
    {
        "soru": "Bir uyuşmazlığı dava açmadan arabuluculuk yoluyla çözebilir miyim?",
        "kanun": "6325",
        "maddeler": [],
    },
    {
        "soru": "Eşim bana şiddet uyguluyor. Uzaklaştırma kararı talep edebilir miyim?",
        "kanun": "6284",
        "maddeler": [],
    },
    {
        "soru": "Engelli bir kişinin erişilebilirlik hakkı konusunda hangi düzenlemeler var?",
        "kanun": "5378",
        "maddeler": [],
    },
    {
        "soru": "İnternette hakkımda yayınlanan bir içerik için erişim engeli talep edilebilir mi?",
        "kanun": "5651",
        "maddeler": [],
    },
    {
        "soru": "İstemediğim halde sürekli reklam mesajı gönderiliyor. Bununla ilgili hakkım var mı?",
        "kanun": "6563",
        "maddeler": [],
    },
]


def test_et(test):
    try:
        response = requests.post(
            URL,
            json={"soru": test["soru"]},
            timeout=60,
        )

        response.raise_for_status()
        data = response.json()

        cevap = str(data.get("cevap", "")).strip()
        kaynaklar = data.get("kaynaklar", [])

        # Gemini gerçekten cevap üretti mi?
        gemini_hatasi = (
            not cevap
            or "Gemini servisi şu anda" in cevap
            or "Gemini cevap uretemedi" in cevap
        )

        bulunan = {
            (
                str(k.get("kanun", "")).split()[0],
                str(k.get("madde", "")),
            )
            for k in kaynaklar
        }

        bulunan_kanunlar = {
            kanun
            for kanun, _ in bulunan
        }

        dogru_kanun = (
            test["kanun"] in bulunan_kanunlar
        )

        # Maddeler verilmişse hepsini zorunlu tutmuyoruz.
        # Beklenen maddelerden en az biri bulunmalı.
        if test["maddeler"]:
            kabul_edilen = {
                (test["kanun"], madde)
                for madde in test["maddeler"]
            }

            bulunan_beklenen = (
                kabul_edilen & bulunan
            )

            dogru_madde = bool(
                bulunan_beklenen
            )
        else:
            kabul_edilen = set()
            bulunan_beklenen = set()
            dogru_madde = True

        basarili = (
            not gemini_hatasi
            and dogru_kanun
            and dogru_madde
        )

        print("\n" + "=" * 70)
        print("SORU:", test["soru"])

        if basarili:
            print("SONUC: BASARILI")
        else:
            print("SONUC: BASARISIZ")

            if gemini_hatasi:
                print(
                    "NEDEN: Gemini geçerli cevap üretemedi."
                )

            if not dogru_kanun:
                print(
                    "BEKLENEN KANUN:",
                    test["kanun"],
                )

            if (
                test["maddeler"]
                and not dogru_madde
            ):
                print(
                    "KABUL EDILEN MADDELER:",
                    test["maddeler"],
                )

        print(
            "BULUNAN:",
            sorted(bulunan),
        )

        if test["maddeler"]:
            print(
                "ESLESEN MADDELER:",
                sorted(bulunan_beklenen),
            )

        print(
            "CEVAP:",
            cevap,
        )

        return basarili

    except Exception as e:
        print("\n" + "=" * 70)
        print("SORU:", test["soru"])
        print("SONUC: HATA")
        print("HATA:", e)

        return False


print(
    "\nHUKUKAI GENISLETILMIS RAG TESTI BASLIYOR..."
)

basarili_sayisi = 0

for test in TESTLER:
    if test_et(test):
        basarili_sayisi += 1

print("\n" + "=" * 70)

print(
    f"TEST SONUCU: "
    f"{basarili_sayisi}/{len(TESTLER)} BASARILI"
)

print("=" * 70)