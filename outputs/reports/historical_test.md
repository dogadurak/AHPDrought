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
Yıl       SPI-12    durum   ort. anomali   risk-anomali ρ   monoton
-------------------------------------------------------------------
1985       -0.86   normal        -0.0478           0.3294     hayır
1986       -0.51   normal        -0.0173           0.0451     hayır
1987        0.05   normal        -0.0301           0.0431     hayır
1988       -0.77   normal        -0.0067          -0.0901     hayır
1989       -2.45    KURAK        -0.0539           0.1847     hayır
1990       -1.37    KURAK        -0.0111          -0.1017     hayır
1991       -0.65   normal         0.0235          -0.0770     hayır
1992       -1.90    KURAK        -0.0515           0.1601     hayır
1993       -0.87   normal        -0.0330           0.1016     hayır
1994       -1.08    KURAK        -0.0329           0.0816     hayır
1995       -0.07   normal         0.0454          -0.1405     hayır
1996       -0.61   normal         0.0260          -0.1970     hayır
1997       -0.41   normal         0.0235          -0.1272      evet
1998        0.09   normal         0.0401          -0.1370     hayır
1999        0.66   normal         0.0112          -0.2358     hayır
2000       -0.99   normal        -0.0163          -0.0730     hayır
2001       -2.30    KURAK         0.0171          -0.2803     hayır
2002        0.98   normal         0.0208          -0.1142     hayır
2003        0.23   normal         0.0006          -0.1738     hayır
2004       -0.24   normal         0.0144          -0.2276     hayır
2005       -0.43   normal         0.0179          -0.0906     hayır
2006       -0.27   normal         0.0003          -0.0822     hayır
2007       -2.35    KURAK        -0.0319          -0.0795     hayır
2008       -1.21    KURAK         0.0062          -0.1125      evet
2009        0.90   normal         0.0074          -0.0208     hayır
2010        1.51   normal         0.0405           0.1201     hayır
2011        0.38   normal         0.0378           0.0028     hayır
-------------------------------------------------------------------
Kurak yıllar  (n=7): ortalama ρ = -0.0211   [1989, 1990, 1992, 1994, 2001, 2007, 2008]
Normal yıllar (n=20): ortalama ρ = -0.0572
Fark: -0.0361  (pozitif = kurak yıllarda ilişki daha güçlü)

Sınıf              kurak yıllar    tüm yıllar
---------------------------------------------
1 — Çok düşük          -0.0218       -0.0000
2 — Düşük              -0.0315       -0.0000
3 — Orta               -0.0310        0.0000
4 — Yüksek             -0.0245        0.0000
5 — Çok yüksek         -0.0203        0.0000
---------------------------------------------
Sınıf 5 eksi Sınıf 1 (beklenti NEGATİF): +0.0015  -> TERS YÖNDE

HİPOTEZ: yapısal risk, ağır stres altında daha güçlü ayrım üretmeli.
SONUÇ  : DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır (ρ = -0.021, eşik ≤ -0.10). Harita ağır stres altında da etkilenen alanları göstermiyor.
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