# Risk Haritasının Gerçek Kuraklıklarda Sınanması

**Dönem:** Landsat 5, 1985–2011 (27 yıl, 30 m)  
**Kurak yıl eşiği:** kurak dönem SPI-12 ≤ -1.0  
**Kapsam:** yalnızca tarım alanı

## Neden bu adım gerekliydi

Adım 11'deki sınama "KARAR VERİLEMEZ" ile bitti: Sentinel-2 döneminde
(2017–2025) yalnızca bir kurak yıl vardı ve o da orta şiddetteydi.
68 yıllık yağış kaydında havzanın gerçek kuraklıkları uydu öncesine
düşüyor:

| Dönem | Süre | En düşük SPI-12 |
|---|---:|---:|
| 1989-01 – 1991-02 | 26 ay | −2,63 |
| 2000-11 – 2001-11 | 13 ay | −2,56 |
| 1991-12 – 1993-01 | 14 ay | −2,29 |
| 2007-01 – 2007-11 | 11 ay | −2,61 |

Landsat 5 (1984–2011) bu dönemi 30 m'de kapsıyor — projenin grid'iyle
birebir aynı çözünürlük.

## Sonuçlar

```
Etki ölçüsü: Landsat 5 yüzey sıcaklığı (enerji dengesi)

Yıl       SPI-12    durum   ort. anomali   risk-anomali r   monoton
-------------------------------------------------------------------
1985       -0.86   normal        -1.9965           0.1111     hayır
1986       -0.51   normal         1.1955           0.0097     hayır
1987        0.05   normal         2.4063          -0.0269     hayır
1988       -0.77   normal         0.3710          -0.1026     hayır
1989       -2.45    KURAK         1.9829           0.0780     hayır
1990       -1.37    KURAK         2.9469           0.0916     hayır
1991       -0.65   normal         2.5808           0.0335     hayır
1992       -1.90    KURAK         3.1014           0.3244     hayır
1993       -0.87   normal         1.2855          -0.0341     hayır
1994       -1.08    KURAK         0.3436           0.2986     hayır
1995       -0.07   normal         3.8013           0.2447     hayır
1996       -0.61   normal         1.3564          -0.2097     hayır
1997       -0.41   normal         0.6285           0.0727     hayır
1998        0.09   normal        -0.2033          -0.1789     hayır
1999        0.66   normal        -0.2293          -0.1112     hayır
2000       -0.99   normal         0.1398          -0.1014     hayır
2001       -2.30    KURAK        -0.5906          -0.1949     hayır
2002        0.98   normal        -4.1442          -0.1174     hayır
2003        0.23   normal         0.1667          -0.1356     hayır
2004       -0.24   normal        -0.4311          -0.0652     hayır
2005       -0.43   normal        -1.4648          -0.2067     hayır
2006       -0.27   normal        -0.5236          -0.0486     hayır
2007       -2.35    KURAK        -3.5966          -0.0923     hayır
2008       -1.21    KURAK        -3.9635          -0.2001     hayır
2009        0.90   normal        -2.4707          -0.0043     hayır
2010        1.51   normal        -2.1848           0.1740     hayır
2011        0.38   normal        -0.5067           0.0113     hayır
-------------------------------------------------------------------
Kurak yıllar  (n=7): ortalama r = +0.0436   [1989, 1990, 1992, 1994, 2001, 2007, 2008]
Normal yıllar (n=20): ortalama r = -0.0343
Fark: -0.0779  (pozitif = kurak yıllarda ilişki daha güçlü)

Sınıf              kurak yıllar    tüm yıllar
---------------------------------------------
1 — Çok düşük           0.2240        0.0000
2 — Düşük               0.0055       -0.0000
3 — Orta                0.0278        0.0000
4 — Yüksek              0.2971       -0.0000
5 — Çok yüksek          0.5637        0.0000
---------------------------------------------
Sınıf 5 eksi Sınıf 1 (beklenti NEGATİF): +0.3397  -> TERS YÖNDE

HİPOTEZ: yapısal risk, ağır stres altında daha güçlü ayrım üretmeli.
SONUÇ  : DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır (r = +0.044, eşik <= -0.10). Harita ağır stres altında da etkilenen alanları göstermiyor.
```

## Bu sınamanın kendi sınırlılıkları

1. **Harita bugünkü verilerle kuruldu.** 1990'ı sınarken "bu mekânsal
   desen 35 yılda değişmedi" varsayımı yapılıyor. Topoğrafya ve toprak
   için güvenli; **sulama ağı ve arazi örtüsü için tartışmalı** — Gediz'de
   sulu tarım o tarihten bu yana genişledi. Sonuç, haritanın *bugünkü*
   hâlinin *geçmişteki* kuraklıkta ne kadar iyi çalışacağını ölçer.
2. **Sensör farkı.** Landsat 5 TM ile Sentinel-2 MSI aynı değeri vermez.
   Bu yüzden anomali Landsat döneminin kendi içinde hesaplanır; iki dönem
   hiçbir yerde karıştırılmaz.
3. **Yüzey sıcaklığı da sulamadan etkilenir.** Sulanan parsel buharlaşmayla serinler; bu ölçü sulamanın maskeleme etkisinden muaf değildir. Ama NDVI ve ET/PET'ten farklı bir fiziksel yoldan (enerji dengesi) ölçtüğü için üçüncü bir bağımsız sınama sağlar. Ayrıca çıplak toprak da sıcaktır: seyrek örtülü alanlarda yüksek sıcaklık stresi değil, örtü azlığını gösterebilir.
4. **Yıl bazındaki anomali sütunu kuraklık göstergesi olarak okunamaz.** Sıcaklık serisi 1985–2011 boyunca ısınma eğilimi taşıyor: 1989 (SPI −2,45) taban çizgisinden soğuk, 2002 (normal) sıcak çıkıyor. Sınamayı bu bozmaz — test yıl İÇİNDE piksel sıralaması üzerinden hesaplanır ve yıla özgü sabit bir kayma sıralamayı değiştirmez. Ancak ısınma mekânsal olarak düzgün dağılmamışsa (kentleşme, sulama alanının genişlemesi) mekânsal deseni de etkileyebilir; bu, ölçünün açık bir sınırıdır.