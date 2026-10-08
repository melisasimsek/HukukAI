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

        timeout=30000

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

Sen HukukAI adlı Türk hukuku bilgi asistanısın.

Kullanıcının sorusunu yalnızca sağlanan mevzuat metinlerine dayanarak cevapla.

KURALLAR:

1. Soruyu doğrudan, sade ve anlaşılır Türkçeyle cevapla.

2. Kaynakta açıkça bulunmayan hak, süre, tazminat, yaptırım,

   parasal tutar, başvuru yolu veya hukuki sonuç üretme.

3. Soru birden fazla hukuki mesele içeriyorsa her birini ayrı değerlendir.

   Her hukuki sonucu yalnızca kendi dayanağı olan maddeyle ilişkilendir.

4. "ONCELIKLI KAYNAK: EVET" işaretli maddeleri önce değerlendir.

   Ancak yalnızca soruyla ilgiliyse kullan.

5. Cevapta gerçekten yararlandığın tüm maddeleri kaynak listesine ekle.

   İlgisiz veya kullanılmayan maddeleri ekleme.

6. Tarafları ve aile ilişkilerini karıştırma. Eksik bilgiler varsa

   varsayım yapma; sonuca etkisini gerektiğinde belirt.

7. Kaynaklar soruyu cevaplamaya yetmiyorsa bunu açıkça söyle.

8. Kullanıcı parasal bir tutar sormuyorsa para tutarlarının

   güncelliğine ilişkin gereksiz uyarılar ekleme.

9. Gerektiğinde kanun ve madde numarasını belirt.

   Kanun metnini uzun uzun kopyalama.

10. Başlık, Markdown tablo veya madde işaretleri kullanma.

    Aynı bilgiyi tekrar etme. Normal düz metin oluştur.

11. Kesin kişisel hukuki danışmanlık yerine genel bilgi sun.

12. Cevabın sonuna şu cümleyi ekle:

    Bu içerik genel bilgilendirme amaçlıdır ve hukuki danışmanlık yerine geçmez.

ÇIKTI:

Yalnızca geçerli JSON döndür.

"kanun" alanında kanun numarasını, "madde" alanında madde numarasını kullan.

JSON yapısı:

{{

  "cevap": "Kullanıcıya gösterilecek hukuki cevap",

  "kullanilan_kaynaklar": [

    {{"kanun": "4857", "madde": "15"}}

  ]

}}

İLGİLİ MEVZUAT:

{belgeler}

KULLANICI SORUSU:

{soru}

    """

    for deneme in range(3):

        baslangic = time.perf_counter()

        try:

            response = client.models.generate_content(

                model="gemini-3.1-flash-lite",

                contents=prompt,

                config=types.GenerateContentConfig(
    temperature=0,
    response_mime_type="application/json",
    max_output_tokens=500,
),

            )

            print(

                f"Gemini cevap süresi: "

                f"{time.perf_counter() - baslangic:.2f} saniye"

            )

            if not response.text:

                raise ValueError(

                    "Gemini boş cevap döndürdü."

                )

            raw_text = json_temizle(response.text)

            data = json.loads(raw_text)

            cevap = str(data.get("cevap", "")).strip()

            kaynaklar = data.get(

                "kullanilan_kaynaklar", []

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

                    temiz_kaynaklar.append({

                        "kanun": kanun,

                        "madde": madde,

                    })

            if cevap:

                return {

                    "cevap": cevap,

                    "kullanilan_kaynaklar": temiz_kaynaklar,

                }

            raise ValueError("Gemini geçerli cevap üretmedi.")

        except Exception as e:

            print(

                f"Gemini deneme {deneme + 1}/3 hatası: {e}"

            )

            print(

                f"Başarısız deneme süresi: "

                f"{time.perf_counter() - baslangic:.2f} saniye"

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

               model="gemini-3.1-flash-lite",

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
