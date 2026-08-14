# Kuraklık İzleme ve Tahmin

**Bölge:** Gediz Havzası — Salihli / Alaşehir / Sarıgöl alt havzası  
**Yağış serisi:** TerraClimate, 1958-01 - 2025-12 (68 yıl)

## Bu modül ne yapar, ne yapmaz

AHP risk haritası *yapısal duyarlılığı* gösterir — nerede kronik olarak
dayanıksız. Bu modül ona **zaman boyutu** ekler:

```
RİSK = TEHLİKE (zamanla değişir) x DUYARLILIK (yapısal)
       ↑ bu modül                  ↑ AHP haritası
```

**Yapmadığı:** dinamik mevsimsel iklim tahmini kullanmaz. ECMWF SEAS5
gibi ürünler kayıt/API anahtarı gerektirdiği için projenin "anahtarsız"
kısıtını kırardı. Buradaki tahmin, serinin kendi otokorelasyonuna
dayanan istatistiksel bir taban çizgisidir.

## 1. SPI

```
SPI-3  (1958-01-01 - 2025-12-01 kalibrasyonu)
  gözlem      : 814 ay
  ortalama    : -0.000   (teorik 0)
  std sapma   : 1.000   (teorik 1)
  aralık      : -2.81 .. +3.41
  kurak ay    : %15.0  (SPI <= -1)
  şiddetli    : %6.0  (SPI <= -1.5)
```

```
SPI-6  (1958-01-01 - 2025-12-01 kalibrasyonu)
  gözlem      : 811 ay
  ortalama    : -0.000   (teorik 0)
  std sapma   : 1.001   (teorik 1)
  aralık      : -2.98 .. +3.50
  kurak ay    : %14.8  (SPI <= -1)
  şiddetli    : %7.8  (SPI <= -1.5)
```

```
SPI-12  (1958-01-01 - 2025-12-01 kalibrasyonu)
  gözlem      : 805 ay
  ortalama    : +0.000   (teorik 0)
  std sapma   : 1.001   (teorik 1)
  aralık      : -2.63 .. +3.18
  kurak ay    : %14.3  (SPI <= -1)
  şiddetli    : %6.5  (SPI <= -1.5)
```

## 2. En şiddetli kuraklık olayları (SPI-12 ≤ −1)

| Başlangıç | Bitiş | Süre (ay) | En düşük SPI | Şiddet |
|---|---|---:|---:|---:|
| 1989-01 | 1991-02 | 26 | -2.63 | -46.3 |
| 2000-11 | 2001-11 | 13 | -2.56 | -26.1 |
| 1991-12 | 1993-01 | 14 | -2.29 | -26.0 |
| 2007-01 | 2007-11 | 11 | -2.61 | -23.6 |
| 1994-02 | 1994-09 | 8 | -1.27 | -8.9 |
| 2022-12 | 2023-04 | 5 | -1.94 | -7.1 |
| 2008-10 | 2009-01 | 4 | -2.35 | -6.6 |
| 2008-05 | 2008-08 | 4 | -1.34 | -5.2 |

## 3. Tahmin becerisi

**Neden taban çizgisi şart.** Kuraklık güçlü otokorelasyonludur; "üç ay
sonra da bugünkü gibi olacak" demek şaşırtıcı derecede iyi çalışır. Bir
yöntemin becerisi mutlak hatayla değil, taban çizgisine göre kazancıyla
ölçülür. Beceri skoru 0'ın altındaysa yöntem referanstan kötüdür.

**Neden kronolojik bölme.** Zaman serisinde rastgele eğitim/test ayrımı
veri sızıntısıdır: komşu aylar birbirine benzer, model ezberler, skor
gerçekte olmayan bir başarı gösterir.

```
Eğitim: 1958-03-01 - 2005-07-01
Test  : 2005-08-01 - 2025-12-01   (kronolojik bölme)

Yöntem                 Ufuk      n        r    RMSE   BS-iklim   BS-kalıcı   isabet   yanlış
--------------------------------------------------------------------------------------------
iklimatoloji              1    245    0.000   1.041      0.000      -0.347     0.00      nan
kalıcılık                 1    245    0.626   0.896      0.259       0.003     0.44     0.55
sönümlü kalıcılık         1    245    0.626   0.810      0.395       0.185     0.18     0.36
iklimatoloji              3    245    0.000   1.041      0.000       0.496     0.00      nan
kalıcılık                 3    245    0.007   1.459     -0.964       0.009     0.23     0.76
sönümlü kalıcılık         3    245   -0.007   1.041     -0.001       0.495     0.00      nan
iklimatoloji              6    245    0.000   1.041      0.000       0.528     0.00      nan
kalıcılık                 6    245   -0.056   1.500     -1.076       0.020     0.18     0.81
sönümlü kalıcılık         6    245   -0.056   1.045     -0.008       0.525     0.00      nan
--------------------------------------------------------------------------------------------
BS = Beceri Skoru (1 - MSE/MSE_referans). 0'in alti, referanstan kotu demektir.
isabet = gerçek kurak ayların yakalanan oranı, yanlış = yanlış alarm oranı.

Sönümleme katsayıları (eğitimden): ρ(1 ay)=0.614, ρ(3 ay)=-0.024, ρ(6 ay)=0.053
```

## 4. Serinin sonundaki durum

- `SPI-3  = -1.28  (Orta kurak)   [2025-12]`
- `SPI-6  = -1.39  (Orta kurak)   [2025-12]`
- `SPI-12 = -2.12  (Olağanüstü kurak)   [2025-12]`

## 5. Mekânsal NDVI anomalisi

```
2024 kurak dönem NDVI anomalisi
  taban çizgisi: [2019, 2020, 2021, 2022, 2023] (5 yıl, hedef yıl dışarıda)
  ortalama z    : -0.192
  aralık        : -81.87 .. +66.88
  maskeli       : %2.31 (taban çizgisi sabit veya veri yok)
  normalin altı : %36.9 (z < -0.5)
  belirgin altı : %24.1 (z < -1.0)

  Sınıf                  Alan payı
  --------------------------------
  Olağanüstü altında          %9.1
  Şiddetli altında            %5.6
  Orta altında                %9.3
  Hafif altında              %12.8
  Normale yakın              %28.2
  Hafif üstünde              %13.8
  Belirgin üstünde           %21.2
```

### Risk haritasının operasyonel sınaması

Yüksek riskli sınıflandırılan alanlar, kurak bir yılda gerçekten daha
fazla mı etkileniyor?

| Risk sınıfı | Ortalama NDVI anomalisi (z) | Piksel |
|---|---:|---:|
| 1 — Çok düşük | -0.167 | 646,684 |
| 2 — Düşük | -0.199 | 1,226,466 |
| 3 — Orta | -0.158 | 1,479,789 |
| 4 — Yüksek | -0.211 | 1,131,614 |
| 5 — Çok yüksek | -0.292 | 552,022 |

- Beş sınıf boyunca monotonluk: **HAYIR**
- Uçlar doğru yönde (sınıf 5 < sınıf 1): **evet**
- Risk indeksi ile anomali arasında Spearman ρ = **-0.0961**

**Yorum.** Uçlar beklenen yönde ama sıralama monoton değil ve
korelasyon zayıf. Bu, ayarlanarak geçirilecek bir sonuç değil;
iki katmanın farklı şeyleri ölçtüğünü gösteriyor:

- Risk haritası 6 yıllık ORTALAMAYA dayanan **yapısal** bir indekstir
  — "burası kronik olarak dayanıksız".
- Anomali ise tek bir yılın kendi geçmişine göre sapmasıdır
  — "bu yıl normalinden ne kadar saptı".

Yapısal olarak kurak bir alan zaten *her yıl* kuraktır; kendi
normaline göre sapması büyük olmak zorunda değildir. Dolayısıyla
tek yılın anomalisi, yapısal risk haritasının zayıf bir sınamasıdır.
Güçlü sınama, birden çok kurak yılın anomalilerinin ortalamasıyla
ya da doğrudan verim verisiyle yapılır (bkz. Sınırlılıklar).

## Sınırlılıklar

1. **Tahmin istatistikseldir, dinamik değildir.** Atmosfer modeli yok;
   yalnızca serinin geçmiş davranışı kullanılıyor.
2. **Mekânsal anomalinin taban çizgisi 6 yıl.** Sentinel-2 arşivi kısa;
   z-skorunun standart sapması az örnekten kestiriliyor. SPI'ın 67 yıllık
   tabanı çok daha sağlamdır.
3. **Havza ölçeğinde tahmin.** TerraClimate ~4 km; bu çözünürlükte piksel
   bazlı tahmin, veride olmayan bir kesinlik iddiası olurdu.