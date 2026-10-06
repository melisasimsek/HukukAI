# anayasa.txt dosyasını aç

with open("dataset/anayasa.txt", "r", encoding="utf-8") as dosya:
    metin = dosya.read()

# Kullanıcının aradığı madde
aranan = "Madde 10"

# Maddeyi ara
konum = metin.find(aranan)

if konum != -1:
    print("Madde bulundu!\n")

    print(metin[konum:konum+1000])

else:
    print("Madde bulunamadı.")