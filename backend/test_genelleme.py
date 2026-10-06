import requests

URL = "http://127.0.0.1:8001/sor"

TESTLER = [
    {
        "soru": "Patronum haftada yedi gün çalışmamı istiyor. Dinlenme hakkım yok mu?",
        "kanun": "4857",
    },
    {
        "soru": "Yeni aldığım telefon arızalı çıktı. Satıcıdan değiştirmesini isteyebilir miyim?",
        "kanun": "6502",
    },
    {
        "soru": "Babam öldü. Annem ve üç kardeşiz. Miras konusunda hangi kanun uygulanır?",
        "kanun": "4721",
    },
    {
        "soru": "Site yönetimine aidat borcum var. Yönetim hakkımda işlem başlatabilir mi?",
        "kanun": "634",
    },
    {
        "soru": "Kaza yaptıktan sonra olay yerinden ayrılabilir miyim?",
        "kanun": "2918",
    },
    {
        "soru": "Borcuma itiraz etmek istiyorum. İcra dairesine başvurabilir miyim?",
        "kanun": "2004",
    },
    {
        "soru": "Memur olarak hakkımda disiplin soruşturması başlatıldı. Hangi kanun uygulanır?",
        "kanun": "657",
    },
    {
        "soru": "Evimin tapu işlemlerini başka bir tapu müdürlüğünden yapabilir miyim?",
        "kanun": "2644",
    },
    {
        "soru": "Belediyeden ruhsat almadan bina yapmaya başladım. İnşaat durdurulabilir mi?",
        "kanun": "3194",
    },
    {
        "soru": "Belediye taşınmazımı kamulaştıracak. Belirlenen bedele ilişkin süreç nasıl işler?",
        "kanun": "2942",
    },
    {
        "soru": "Türkiye'de uzun süre kalmak isteyen yabancı hangi izinle kalabilir?",
        "kanun": "6458",
    },
    {
        "soru": "Mahkemeye gitmeden karşı tarafla anlaşmak için arabulucuya başvurabilir miyim?",
        "kanun": "6325",
    },
    {
        "soru": "Eski eşim beni sürekli takip ediyor ve tehdit ediyor. Koruma kararı alabilir miyim?",
        "kanun": "6284",
    },
    {
        "soru": "Engelli bireylerin toplu taşıma araçlarına erişilebilir olması zorunlu mu?",
        "kanun": "5378",
    },
    {
        "soru": "Bir internet sitesindeki hukuka aykırı içeriğin kaldırılmasını isteyebilir miyim?",
        "kanun": "5651",
    },
    {
        "soru": "Bir şirket iznim olmadan sürekli kampanya SMS'i gönderiyor. Bunu reddedebilir miyim?",
        "kanun": "6563",
    },
    {
        "soru": "Birisi telefonumu iznim olmadan aldı ve geri vermiyor. Bu durum hangi suç kapsamında olabilir?",
        "kanun": "5237",
    },
    {
        "soru": "Bir kişi bana mesaj yoluyla ağır küfürler etti. Bunun ceza hukukunda karşılığı var mı?",
        "kanun": "5237",
    },
    {
        "soru": "Telefon numaram ve adresim iznim olmadan bir şirkete verilmiş. Kişisel verilerim korunuyor mu?",
        "kanun": "6698",
    },
    {
        "soru": "İş kazası geçiren sigortalının sosyal güvenlik açısından hakları hangi kanunda düzenleniyor?",
        "kanun": "5510",
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

        cevap = str(
            data.get("cevap", "")
        ).strip()

        kaynaklar = data.get(
            "kaynaklar",
            [],
        )

        bulunan = {
            str(
                kaynak.get(
                    "kanun",
                    "",
                )
            ).split()[0]
            for kaynak in kaynaklar
        }

        gemini_hatasi = (
            not cevap
            or "Gemini servisi şu anda" in cevap
        )

        basarili = (
            test["kanun"] in bulunan
            and not gemini_hatasi
        )

        print("\n" + "=" * 70)
        print("SORU:", test["soru"])

        if basarili:
            print("SONUC: BASARILI")
        else:
            print("SONUC: BASARISIZ")
            print(
                "BEKLENEN KANUN:",
                test["kanun"],
            )

        print(
            "BULUNAN KANUNLAR:",
            sorted(bulunan),
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
    "\nHUKUKAI GENELLEME TESTI BASLIYOR..."
)

basarili = 0

for test in TESTLER:
    if test_et(test):
        basarili += 1

print("\n" + "=" * 70)

print(
    f"GENELLEME TEST SONUCU: "
    f"{basarili}/{len(TESTLER)} BASARILI"
)

print("=" * 70)