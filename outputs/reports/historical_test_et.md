# Risk Haritasının Gerçek Kuraklıklarda Sınanması

**Dönem:** Landsat 5, 2000–2024 (25 yıl, 30 m)  
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
Etki ölçüsü: MODIS ET/PET (su kısıtı)

Yıl       SPI-12    durum   ort. anomali   risk-anomali ρ   monoton
-------------------------------------------------------------------
2000       -0.99   normal        -0.0352           0.1022     hayır
2001       -2.30    KURAK        -0.0328          -0.2058     hayır
2002        0.98   normal         0.0264          -0.2200      evet
2003        0.23   normal        -0.0042          -0.0233     hayır
2004       -0.24   normal        -0.0060          -0.2019     hayır
2005       -0.43   normal         0.0077          -0.3091     hayır
2006       -0.27   normal         0.0142          -0.2446     hayır
2007       -2.35    KURAK        -0.0580           0.1968     hayır
2008       -1.21    KURAK        -0.0285           0.1576     hayır
2009        0.90   normal         0.0133           0.0888     hayır
2010        1.51   normal        -0.0005           0.2764     hayır
2011        0.38   normal         0.0083           0.1687     hayır
2012        0.91   normal         0.0004          -0.2238     hayır
2013        0.58   normal         0.0001           0.0054     hayır
2014       -0.80   normal         0.0311          -0.3475     hayır
2015        1.33   normal         0.0371          -0.2130     hayır
2016       -0.16   normal        -0.0212           0.1203     hayır
2017       -0.29   normal         0.0044          -0.0124     hayır
2018       -0.03   normal         0.0042           0.3009     hayır
2019        0.56   normal         0.0108           0.0818     hayır
2020       -0.35   normal        -0.0063           0.1390     hayır
2021       -0.48   normal        -0.0133           0.3529     hayır
2022       -0.04   normal        -0.0049           0.0777     hayır
2023        0.26   normal         0.0654           0.3223     hayır
2024       -0.09   normal        -0.0128           0.0849     hayır
-------------------------------------------------------------------
Kurak yıllar  (n=3): ortalama ρ = +0.0495   [2001, 2007, 2008]
Normal yıllar (n=22): ortalama ρ = +0.0148
Fark: -0.0347  (pozitif = kurak yıllarda ilişki daha güçlü)

Sınıf              kurak yıllar    tüm yıllar
---------------------------------------------
1 — Çok düşük          -0.0390        0.0000
2 — Düşük              -0.0396       -0.0000
3 — Orta               -0.0423       -0.0000
4 — Yüksek             -0.0389        0.0000
5 — Çok yüksek         -0.0378        0.0000
---------------------------------------------
Sınıf 5 eksi Sınıf 1 (beklenti NEGATİF): +0.0011  -> TERS YÖNDE

HİPOTEZ: yapısal risk, ağır stres altında daha güçlü ayrım üretmeli.
SONUÇ  : DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır (ρ = +0.050, eşik ≤ -0.10). Harita ağır stres altında da etkilenen alanları göstermiyor.
```

## Bu sınamanın kendi sınırlılıkları

1. **Harita bugünkü verilerle kuruldu.** 1990'ı sınarken "bu mekânsal
   desen 35 yılda değişmedi" varsayımı yapılıyor. Topoğrafya ve toprak
   için güvenli; **sulama ağı ve arazi örtüsü için tartışmalı** — Gediz'de
   sulu tarım o tarihten bu yana genişledi. Sonuç, haritanın *bugünkü*
   hâlinin *geçmişteki* kuraklıkta ne kadar iyi çalışacağını ölçer.
2. **Sensör farkı.** Landsat 5 TM ile Sentinel-2 MSI aynı NDVI'ı vermez.
   Bu yüzden anomali Landsat döneminin kendi içinde hesaplanır; iki dönem
   hiçbir yerde karıştırılmaz.
3. **NDVI hâlâ dolaylı bir etki ölçüsüdür.** Sulanan parselde yeşillik
   korunurken maliyet artmış olabilir (bkz. Adım 11).