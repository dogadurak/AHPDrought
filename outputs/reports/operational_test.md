# Risk Haritasının Çok Yıllı Operasyonel Sınaması

**Senaryo:** `steep_riskier`  
**Yıllar:** [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]  
**Kurak yıl eşiği:** yaz ortalaması SPI-3 ≤ -0.5

## Neden bu sınama, öncekinden farklı

İlk sürümde tek bir yılın (2024) anomalisi risk sınıflarına göre
özetlendi ve monoton çıkmadığı için "doğrulanmadı" denildi. İki kusuru
vardı: dokuz yıllık veriden yalnızca birini kullanıyordu ve yanlış bir
beklenti taşıyordu.

Yapısal bir duyarlılık haritasının HER yıl etki öngörmesi beklenemez.
Yağışlı bir yılda kimse zorlanmaz; duyarlılık farkı görünmez. Harita
ancak **stres varken** ayrım üretmelidir. Sınanabilir hipotez budur:

> Risk ile gözlenen bitki örtüsü kaybı arasındaki ilişki, kurak
> yıllarda yağışlı yıllara göre belirgin şekilde güçlü olmalıdır.

Yıllar, modele hiç girmemiş bir ölçütle (havza yağışından türeyen SPI)
etiketlenir — aksi halde sınama kendi kendini doğrulardı.

## Yıl bazında sonuçlar

| Yıl | Yaz SPI-3 | Durum | Ort. anomali | risk–anomali ρ | Monoton |
|---|---:|---|---:|---:|---|
| 2017 | -0.73 | **KURAK** | -0.289 | +0.0119 | hayır |
| 2018 | -0.75 | **KURAK** | -0.332 | +0.0757 | hayır |
| 2019 | -1.54 | **KURAK** | +0.139 | +0.0088 | hayır |
| 2020 | -0.31 | yağışlı | +0.117 | -0.0679 | hayır |
| 2021 | +0.25 | yağışlı | -0.226 | -0.1079 | hayır |
| 2022 | -0.72 | **KURAK** | -0.094 | -0.0341 | hayır |
| 2023 | +0.43 | yağışlı | +0.921 | +0.1070 | hayır |
| 2024 | -1.42 | **KURAK** | +0.042 | -0.0919 | hayır |
| 2025 | -1.46 | **KURAK** | -0.344 | -0.0318 | hayır |

### z-skoru ile

```
Yıl       SPI     durum   ort. anomali   risk-anomali ρ   monoton
-----------------------------------------------------------------
2017    -0.73     KURAK         -0.289           0.0119     hayır
2018    -0.75     KURAK         -0.332           0.0757     hayır
2019    -1.54     KURAK          0.139           0.0088     hayır
2020    -0.31   yağışlı          0.117          -0.0679     hayır
2021     0.25   yağışlı         -0.226          -0.1079     hayır
2022    -0.72     KURAK         -0.094          -0.0341     hayır
2023     0.43   yağışlı          0.921           0.1070     hayır
2024    -1.42     KURAK          0.042          -0.0919     hayır
2025    -1.46     KURAK         -0.344          -0.0318     hayır
-----------------------------------------------------------------
Kurak yıllar   (n=6): ortalama ρ = -0.0102   [2017, 2018, 2019, 2022, 2024, 2025]
Yağışlı yıllar (n=3): ortalama ρ = -0.0229   [2020, 2021, 2023]
Fark: -0.0127  (pozitif = kurak yıllarda ilişki daha güçlü)

HİPOTEZ: yapısal risk, stres varken daha güçlü ayrım üretmeli.
SONUÇ  : DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır (ρ = -0.010, anlamlı sayılması için ≤ -0.10 olmalıydı). Harita etkilenen alanları göstermiyor.
```

### Ham NDVI farkı ile

z-skoru her pikseli **kendi** değişkenliğine böler. Yapısal olarak kurak
bir piksel zaten hep kuraktır, varyansı düşüktür ve büyük bir z üretemez;
orman ya da sulanan tarımın ise kaybedecek NDVI'ı vardır. Bu, z-skorunu
risk haritasının sınamasında **ters yönde** çalıştırabilir. Ham fark bu
yanlılığı taşımaz.

```
Yıl       SPI     durum   ort. anomali   risk-anomali ρ   monoton
-----------------------------------------------------------------
2017    -0.73     KURAK         -0.007          -0.0088     hayır
2018    -0.75     KURAK         -0.011           0.0506     hayır
2019    -1.54     KURAK          0.007          -0.0227     hayır
2020    -0.31   yağışlı          0.007          -0.0887     hayır
2021     0.25   yağışlı         -0.008          -0.1018     hayır
2022    -0.72     KURAK         -0.001          -0.0500     hayır
2023     0.43   yağışlı          0.029           0.0146     hayır
2024    -1.42     KURAK         -0.002          -0.1000     hayır
2025    -1.46     KURAK         -0.014          -0.0417     hayır
-----------------------------------------------------------------
Kurak yıllar   (n=6): ortalama ρ = -0.0288   [2017, 2018, 2019, 2022, 2024, 2025]
Yağışlı yıllar (n=3): ortalama ρ = -0.0586   [2020, 2021, 2023]
Fark: -0.0298  (pozitif = kurak yıllarda ilişki daha güçlü)

HİPOTEZ: yapısal risk, stres varken daha güçlü ayrım üretmeli.
SONUÇ  : DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır (ρ = -0.029, anlamlı sayılması için ≤ -0.10 olmalıydı). Harita etkilenen alanları göstermiyor.
```

### Yalnızca tarım alanı (arazi örtüsü 40), ham NDVI farkı

NDVI kaybı, farklı bitki yoğunluklarındaki alanlar arasında **adil bir
etki ölçüsü değildir**: NDVI'ı zaten 0,15 olan çıplak bir piksel 0,3 birim
kaybedemez; ormanın ya da sulanan tarımın kaybedecek çok şeyi vardır. Bu
taban/tavan etkisi yüksek riskli (seyrek örtülü) alanları sistematik olarak
"az etkilenmiş" gösterir ve havza genelinde ölçülen ters yönlü ilişkinin
büyük kısmını açıklar.

Tek bir arazi örtüsü sınıfı içinde karşılaştırma bu yanlılığı kaldırır:
benzer yoğunluktaki parseller birbiriyle kıyaslanır. Tarımsal kuraklık
çalışması olduğu için doğal seçim `Cropland`tir.

```
Yıl       SPI     durum   ort. anomali   risk-anomali ρ   monoton
-----------------------------------------------------------------
2017    -0.73     KURAK          0.009          -0.0492     hayır
2018    -0.75     KURAK         -0.005           0.0096     hayır
2019    -1.54     KURAK          0.009          -0.0079     hayır
2020    -0.31   yağışlı          0.009          -0.0415     hayır
2021     0.25   yağışlı         -0.006          -0.1103     hayır
2022    -0.72     KURAK          0.005          -0.0040     hayır
2023     0.43   yağışlı          0.016           0.0146     hayır
2024    -1.42     KURAK         -0.016          -0.1650      evet
2025    -1.46     KURAK         -0.020          -0.1168      evet
-----------------------------------------------------------------
Kurak yıllar   (n=6): ortalama ρ = -0.0555   [2017, 2018, 2019, 2022, 2024, 2025]
Yağışlı yıllar (n=3): ortalama ρ = -0.0457   [2020, 2021, 2023]
Fark: +0.0099  (pozitif = kurak yıllarda ilişki daha güçlü)

HİPOTEZ: yapısal risk, stres varken daha güçlü ayrım üretmeli.
SONUÇ  : DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır (ρ = -0.056, anlamlı sayılması için ≤ -0.10 olmalıydı). Harita etkilenen alanları göstermiyor.
```

### Yağmura bağlı tarım (sulama şebekesinden uzak)

Ölçülen değerler, kurak yıllarda tarım alanı NDVI anomalisi:

| Yıl | Kanala <2 km | Kanaldan >10 km | Oran |
|---|---:|---:|---:|
| 2024 (kurak) | −0,0043 | **−0,0428** | 10× |
| 2025 (kurak) | −0,0151 | **−0,0315** | 2× |
| 2023 (yağışlı) | +0,0146 | +0,0177 | fark yok |

**Sulama, NDVI'daki kuraklık sinyalini maskeliyor.** Çiftçi sularsa
yeşillik korunur; etki suya, maliyete ve rezervuar seviyesine yansır,
spektruma değil. Yağışlı yılda iki grup arasında fark olmaması bunu
doğruluyor — fark yalnızca stres varken ortaya çıkıyor.

Bu, havza geneli sınamanın neden başarısız olduğunu açıklıyor: haritanın
"düşük risk" dediği yerde sulama koruyor, "yüksek risk" dediği seyrek
örtüde zaten düşecek NDVI yok. Sinyal ancak yağmura bağlı tarımda
ölçülebilir.

```
Yıl       SPI     durum   ort. anomali   risk-anomali ρ   monoton
-----------------------------------------------------------------
2017    -0.73     KURAK          0.010          -0.0917     hayır
2018    -0.75     KURAK          0.008          -0.0950     hayır
2019    -1.54     KURAK          0.012          -0.0713     hayır
2020    -0.31   yağışlı          0.011          -0.0863     hayır
2021     0.25   yağışlı         -0.008          -0.0671     hayır
2022    -0.72     KURAK          0.024           0.0203     hayır
2023     0.43   yağışlı          0.018          -0.0098     hayır
2024    -1.42     KURAK         -0.043          -0.0492     hayır
2025    -1.46     KURAK         -0.032          -0.0692     hayır
-----------------------------------------------------------------
Kurak yıllar   (n=6): ortalama ρ = -0.0593   [2017, 2018, 2019, 2022, 2024, 2025]
Yağışlı yıllar (n=3): ortalama ρ = -0.0544   [2020, 2021, 2023]
Fark: +0.0049  (pozitif = kurak yıllarda ilişki daha güçlü)

HİPOTEZ: yapısal risk, stres varken daha güçlü ayrım üretmeli.
SONUÇ  : DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır (ρ = -0.059, anlamlı sayılması için ≤ -0.10 olmalıydı). Harita etkilenen alanları göstermiyor.
```

## Kurak yıllar havuzlanmış

Tek yılın gürültüsü yerine stres altındaki yılların ağırlıklı ortalaması.

| Risk sınıfı | Kurak yıllar | Tüm yıllar |
|---|---:|---:|
| 1 — Çok düşük | -0.177 | -0.045 |
| 2 — Düşük | -0.175 | -0.028 |
| 3 — Orta | -0.161 | -0.009 |
| 4 — Yüksek | -0.123 | +0.016 |
| 5 — Çok yüksek | -0.078 | +0.048 |

## Sınırlılıklar

1. **Az sayıda yıl.** 6 kurak, 3 yağışlı yıl.
   İki grubun ortalaması karşılaştırılıyor; istatistiksel güç düşüktür
   ve sonuç eğilim olarak okunmalıdır, kesin kanıt olarak değil.
2. **Anomali, etkinin dolaylı ölçüsüdür.** NDVI kaybı verim kaybına eşit
   değildir; sulanan parselde NDVI korunurken maliyet artmış olabilir.
3. **Kurak/yağışlı etiketi havza ortalamasıdır.** Havza içi mekânsal
   yağış farkları bu etikete girmiyor.