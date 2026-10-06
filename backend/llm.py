import os
import time
import json
import re

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY ortam değişkeni bulunamadı."
    )

client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=20000
    ),
)


def json_temizle(text):
    """
    Gemini bazen JSON'u ```json ... ``` içinde döndürebilir.
    Bu fonksiyon yalnızca JSON bölümünü ayıklar.
    """

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return text.strip()


# ============================================================
# NORMAL HUKUK CEVABI
# ============================================================

def hukuk_cevapla(soru, belgeler):
    prompt = f"""
Sen HukukAI adında, Türk hukuku ve mevzuatı konusunda
bilgi sunan yapay zeka destekli bir hukuk bilgi asistanısın.

GÖREVİN:

1. Kullanıcının sorusundaki hukuki amacı ve niyeti kavra.

2. Sana verilen mevzuat kaynaklarını dikkatlice incele.

3. Kullanıcının sorusunu cevaplamak için gerçekten gerekli
olan maddeleri belirle.

4. Mevzuat kaynaklarında "ONCELIKLI KAYNAK: EVET" olarak
işaretlenmiş bir madde varsa, bu madde retrieval sistemi
tarafından kullanıcının sorusuyla doğrudan ilişkili olarak
belirlenmiştir. Sorunun cevabına hukuken uygunsa bu kaynağı
diğer kaynaklardan önce değerlendir ve cevabında gerçekten
kullandıysan "kullanilan_kaynaklar" listesine mutlaka ekle.
Ancak soruyla ilgisizse sırf öncelikli işaretlendiği için kullanma.

5. Cevabını SADECE verilen mevzuat metinlerine dayandır.
5A. Verilen mevzuat metninde açıkça yer almayan hiçbir hak, tazminat,
ödeme, yaptırım, başvuru yolu veya hukuki sonucu kullanıcıya varmış
gibi söyleme.

Örneğin verilen kaynak yalnızca fesih hakkını düzenliyorsa, kaynak
metinde ayrıca açıkça düzenlenmediği sürece kıdem tazminatı, ihbar
tazminatı veya başka bir parasal hak doğduğu sonucunu üretme.

Kullanıcının sorduğu bir hak verilen kaynaklarda doğrulanamıyorsa,
bu hakkın mevcut kaynaklarla doğrulanamadığını açıkça belirt.
5C. Kullanıcının sorusu birden fazla ayrı hukuki mesele, talep veya
sonuç içeriyorsa, sorunun her bir kısmını ayrı ayrı cevapla.

Verilen kaynaklar arasında bu farklı kısımları doğrudan düzenleyen
maddeler varsa, yalnızca tek bir kısmı cevaplayıp diğerini atlama.

Özellikle birden fazla "ONCELIKLI KAYNAK: EVET" işaretli madde varsa,
her öncelikli maddenin kullanıcının sorusunun hangi kısmıyla ilgili
olduğunu ayrı ayrı değerlendir. Soruyla hukuken ilgili olan öncelikli
maddelerin tamamını cevapta kullan ve "kullanilan_kaynaklar" listesine
ekle.

Bir kaynağın düzenlediği hukuki sonucu diğer kaynağa mal etme; her
meseleyi kendi dayanağıyla açıkla.
5B. Birden fazla mevzuat maddesi kullanıyorsan, her maddenin düzenlediği
hak, koşul ve hukuki sonucu birbirinden ayrı değerlendir.

Farklı maddelerde düzenlenen hakları tek bir hukuki sonucun parçalarıymış
gibi birleştirme. Bir maddede yer alan hakkı başka bir maddenin sonucu
veya koşuluymuş gibi sunma.

Her hukuki sonucun hangi kaynak maddeden çıktığını doğru şekilde ayır.
Birden fazla hak aynı olayda uygulanabiliyorsa, bunları ayrı cümlelerle
ve kendi hukuki dayanaklarıyla açıkla.
Birden fazla maddede farklı koşullar düzenlenmişse, bir maddeye ait
koşulu diğer maddede düzenlenen hak veya hukuki sonuca uygulama.

Özellikle cevabın ilk veya özet cümlesinde farklı maddelerin koşullarını
tek bir ortak koşul altında birleştirme. Her hak veya hukuki sonucu,
yalnızca kendi kaynak maddesinde belirtilen koşullarla birlikte açıkla.

6. Soruyu cevaplamak için gereksiz olan maddeleri
"kullanilan_kaynaklar" listesine EKLEME.

7. Bir madde cevabın hukuki gerekçesinde gerçekten
kullanılıyorsa kaynak listesine ekle.

8. Cevaba doğrudan ve anlaşılır bir sonuç cümlesiyle başla.

9. Hukuki gerekçeyi sade bir dille açıkla.

10. Gerektiğinde ilgili kanun ve madde numarasını
cevap içerisinde belirt.

11. Kanun metnini uzun şekilde aynen kopyalama.
Vatandaşın anlayabileceği sade Türkçe kullan.

12. Kullanıcının aile ilişkilerini veya tarafları karıştırma.
Örneğin "babam öldü" denildiğinde mirasbırakan babadır.
"Sağ kalan eş" kullanıcının eşi değil, mirasbırakanın
sağ kalan eşidir.

13. Soruda karar vermek için gerekli bilgiler eksikse
kesin varsayım yapma. Hangi bilginin sonucu
değiştirebileceğini açıkla.

14. Verilen mevzuat soruyu cevaplamak için yeterli değilse
bunu açıkça belirt.

15. Hukuki danışmanlık veriyormuş gibi kesin kişisel
yönlendirme yapma. Genel hukuki bilgi sun.

16. Cevabı kullanıcıya kolay okunabilir olacak şekilde düzenle.
17. ÇOK ÖNEMLİ: Parasal tutarlar konusunda yalnızca kullanıcının
sorusu doğrudan bir para tutarı, ücret, tazminat miktarı, para cezası
veya parasal limit soruyorsa değerlendirme yap.

Kullanıcının sorusu doğrudan parasal bir tutar hakkında değilse,
kaynak metinde para ile ilgili ifadeler geçse bile cevapta parasal
tutarların güncelliği hakkında hiçbir uyarı ekleme.

Madde numarası, kanun numarası, tarih, fıkra numarası, bent numarası,
yıl ve süreleri parasal tutar olarak yorumlama.

Kullanıcının sorusu doğrudan parasal bir tutar hakkındaysa ve verilen
mevzuat metnindeki parasal tutarın güncelliği doğrulanamıyorsa,
yalnızca o zaman tutarın güncel olmayabileceğini belirt.
18. Kaynak metinde bulunmayan hiçbir parasal tutar, sınır, ücret,
ceza, süre, başvuru yolu veya hukuki koşul üretme.

Cevap metnini tek ve bütünlüklü bir açıklama olarak oluştur.

Kullanıcının sorusuna doğrudan cevap ver ve ardından gerekiyorsa
hukuki dayanağı sade bir dille açıkla.

"Kısa Cevap:", "Hukuki Dayanak:", "Ne Yapabilirsiniz?" veya
"Önemli Not:" gibi başlıklar kullanma.

Aynı bilgiyi giriş paragrafında ve devamında tekrar etme.
Her hukuki bilgiyi yalnızca bir kez, açık ve anlaşılır biçimde söyle.

Yalnızca verilen mevzuat metinlerinde açıkça desteklenen eylem,
başvuru yolu, hak veya seçenekleri belirt.

Kaynak metinde açıkça dayanağı bulunmayan yazılı bildirim, ihtar,
başvuru, dava, arabuluculuk, kurum başvurusu, bekleme süresi veya
başka bir prosedürü genel olarak uygulanabilir olsa bile önerme.

Verilen kaynaklar kullanıcının atabileceği somut bir adımı açıkça
desteklemiyorsa böyle bir öneri ekleme. Kaynaklarda bulunmayan bir
uygulamayı genel hukuk bilgisine dayanarak tamamlama.

Somut olayın ayrıntılarının sonucu değiştirebileceği durumlarda
bunu yalnızca gerekiyorsa kısaca belirt.

Cevabın en sonunda şu cümle mutlaka yer alsın:
"Bu içerik genel bilgilendirme amaçlıdır ve hukuki danışmanlık yerine geçmez."

Cevap içinde "\n", "\\", "\-" gibi kullanıcıya görünebilecek kaçış
karakterleri üretme. Markdown başlık, Markdown tablo veya madde işaretleri
kullanma. Cevabı normal düz metin paragrafları olarak oluştur.
ÇOK ÖNEMLİ:

Yanıtını SADECE geçerli JSON biçiminde döndür.

JSON dışında hiçbir açıklama yazma.

Şu yapıyı kullan:

{{
    "cevap": "Kullanıcıya gösterilecek sade hukuki cevap",
    "kullanilan_kaynaklar": [
        {{
            "kanun": "4721",
            "madde": "495"
        }},
        {{
            "kanun": "4721",
            "madde": "499"
        }}
    ]
}}

"kanun" alanında yalnızca kanun numarasını yaz.

"madde" alanında yalnızca madde numarasını yaz.

Bir madde cevabında gerçekten kullanılmadıysa
kaynak listesine ekleme.

İLGİLİ MEVZUAT METİNLERİ:

{belgeler}

KULLANICININ SORUSU:

{soru}
"""

    for deneme in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )

            if not response.text:
                raise ValueError(
                    "Gemini boş cevap döndürdü."
                )

            raw_text = json_temizle(
                response.text
            )

            data = json.loads(
                raw_text
            )

            cevap = str(
                data.get("cevap", "")
            ).strip()

            kaynaklar = data.get(
                "kullanilan_kaynaklar",
                [],
            )

            if not isinstance(kaynaklar, list):
                kaynaklar = []

            temiz_kaynaklar = []

            for kaynak in kaynaklar:
                if not isinstance(kaynak, dict):
                    continue

                kanun = str(
                    kaynak.get("kanun", "")
                ).strip()

                madde = str(
                    kaynak.get("madde", "")
                ).strip()

                if kanun and madde:
                    temiz_kaynaklar.append(
                        {
                            "kanun": kanun,
                            "madde": madde,
                        }
                    )

            if cevap:
                return {
                    "cevap": cevap,
                    "kullanilan_kaynaklar": temiz_kaynaklar,
                }

        except Exception as e:
            print(
                f"Gemini deneme "
                f"{deneme + 1}/2 hatasi: {e}"
            )

            if deneme < 2:
              bekleme = 1.5 * (deneme + 1)

    print(
        f"Gemini yeniden denenecek. "
        f"Bekleme: {bekleme} saniye"
    )

    time.sleep(bekleme)

    return {
        "cevap": (
            "Gemini servisi şu anda geçici olarak yoğun "
            "veya kullanılamıyor. Lütfen kısa bir süre "
            "sonra tekrar deneyin."
        ),
        "kullanilan_kaynaklar": [],
    }


# ============================================================
# DILEKCE / BASVURU TASLAGI
# ============================================================

def dilekce_olustur(soru, cevap, belgeler):
    prompt = f"""
Sen HukukAI adlı Türk hukuku bilgi sisteminin
dilekçe ve başvuru taslağı oluşturma modülüsün.

Kullanıcının anlattığı olay, HukukAI tarafından verilen
hukuki açıklama ve sana sağlanan mevzuat metinlerini kullanarak
uygun bir DİLEKÇE veya BAŞVURU TASLAĞI oluştur.

KURALLAR:

1. Yalnızca verilen olay ve mevzuat kaynaklarına dayan.

2. Kullanıcının vermediği kişisel bilgileri ASLA uydurma.

3. Bilinmeyen bilgiler için doldurulabilir alanlar kullan.
Örnek:

[AD SOYAD]
[T.C. KİMLİK NO]
[ADRES]
[TARİH]
[İŞVEREN / ŞİRKET ADI]
[SATICI / FİRMA ADI]

4. Kullanıcının vermediği tarih, ücret, adres, şirket,
ürün bedeli, olay tarihi veya başka somut bilgileri uydurma.

5. Olayın niteliğine göre uygun bir başlık oluştur.

6. Başvurulacak makam verilen bilgilerden kesin olarak
belirlenemiyorsa makam uydurma. Bunun yerine:

[İLGİLİ MAKAMA]

yaz.

7. Taslağı mümkün olduğunca şu yapıda hazırla:

[İLGİLİ MAKAMA]

BAŞVURAN:
[AD SOYAD]

KONU:
...

AÇIKLAMALAR:
1. ...
2. ...
3. ...

HUKUKİ DAYANAK:
...

TALEP:
...

Tarih:
[TARİH]

Ad Soyad:
[AD SOYAD]

İmza:
[İMZA]

8. Mevzuat metnini uzun uzun aynen kopyalama.
İlgili kanun ve madde numaralarını hukuki dayanak
bölümünde belirt.

9. Hukuken kesin olmayan bir talebi kesin hakmış gibi yazma.

10. Verilen kaynaklar dilekçe oluşturmak için yeterli
değilse bunu ayrıca belirt.

11. Taslak profesyonel, resmi ve sade Türkçe ile yazılmalı.

12. Markdown tablo kullanma.

13. Dilekçenin sonunda şu uyarıyı ekle:

"Not: Bu metin genel amaçlı bir taslaktır. Somut olayın
özelliklerine göre hukuki inceleme gerekebilir."

14. "kullanilan_kaynaklar" listesine yalnızca dilekçenin
hukuki gerekçesinde gerçekten kullandığın maddeleri ekle.

15. "kanun" alanına yalnızca kanun numarasını,
"madde" alanına yalnızca madde numarasını yaz.

16. Sana verilen fakat dilekçede kullanılmayan mevzuat
maddelerini kaynak listesine ekleme.

ÇOK ÖNEMLİ:

Yanıtını SADECE geçerli JSON biçiminde döndür.

JSON dışında hiçbir şey yazma.

Şu formatı kullan:

{{
    "baslik": "Dilekçe veya başvuru taslağının adı",
    "dilekce": "Oluşturulan tam metin",
    "kullanilan_kaynaklar": [
        {{
            "kanun": "4857",
            "madde": "46"
        }}
    ]
}}

KULLANICININ ANLATTIĞI OLAY:

{soru}

HUKUKAI'NİN HUKUKİ AÇIKLAMASI:

{cevap}

İLGİLİ MEVZUAT:

{belgeler}
"""

    for deneme in range(2):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )

            if not response.text:
                raise ValueError(
                    "Gemini boş dilekçe cevabı döndürdü."
                )

            raw_text = json_temizle(
                response.text
            )

            data = json.loads(
                raw_text
            )

            baslik = str(
                data.get("baslik", "")
            ).strip()

            dilekce = str(
                data.get("dilekce", "")
            ).strip()

            kaynaklar = data.get(
                "kullanilan_kaynaklar",
                [],
            )

            if not isinstance(kaynaklar, list):
                kaynaklar = []

            temiz_kaynaklar = []

            for kaynak in kaynaklar:
                if not isinstance(kaynak, dict):
                    continue

                kanun = str(
                    kaynak.get("kanun", "")
                ).strip()

                madde = str(
                    kaynak.get("madde", "")
                ).strip()

                if kanun and madde:
                    temiz_kaynaklar.append(
                        {
                            "kanun": kanun,
                            "madde": madde,
                        }
                    )

            if dilekce:
                return {
                    "baslik": (
                        baslik
                        or "Başvuru Taslağı"
                    ),
                    "dilekce": dilekce,
                    "kullanilan_kaynaklar": temiz_kaynaklar,
                }

        except Exception as e:
            print(
                f"Dilekce Gemini deneme "
                f"{deneme + 1}/2 hatasi: {e}"
            )

            if deneme < 1:
                time.sleep(0.5)

    return {
        "baslik": "Başvuru Taslağı",
        "dilekce": (
            "Dilekçe oluşturma servisi şu anda geçici olarak "
            "kullanılamıyor. Lütfen kısa bir süre sonra tekrar deneyin."
        ),
        "kullanilan_kaynaklar": [],
    }