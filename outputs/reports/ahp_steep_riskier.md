# AHP Kuraklık Risk Analizi — senaryo `steep_riskier`

**Bölge:** Gediz Havzası — Salihli / Alaşehir / Sarıgöl alt havzası  
**Grid:** EPSG:32635, 30 m  
**Referans yılları:** [2019, 2020, 2021, 2022, 2023, 2024]

## 1. AHP ağırlıkları

```
Kriter                   Ağırlık
--------------------------------
precipitation             0.2135
irrigation_access         0.1782
ndvi_dry                  0.1585
soil_awc                  0.1336
lst                       0.1117
landcover                 0.0843
distance_to_water         0.0523
slope                     0.0425
aspect                    0.0254
--------------------------------
TOPLAM                    1.0000

lambda_max = 9.1073   (n = 9)
CI         = 0.0134
RI         = 1.4500
CR         = 0.0093
```

Tutarlılık oranı CR = 0.0093 (eşik 0.1) — matris kabul edildi.

## 2. Nominal ağırlık ve efektif katkı

```
Kriter                Ağırlık   Kullanılan aralık   Efektif katkı
-----------------------------------------------------------------
precipitation          0.2135         0.00 - 1.00           %24.5
ndvi_dry               0.1585         0.00 - 1.00           %16.5
irrigation_access      0.1782         0.00 - 1.00           %16.0
soil_awc               0.1336         0.00 - 1.00           %12.2
lst                    0.1117         0.00 - 1.00           %11.4
landcover              0.0843         0.10 - 1.00            %8.9
slope                  0.0425         0.00 - 1.00            %4.6
aspect                 0.0254         0.00 - 1.00            %3.1
distance_to_water      0.0523         0.00 - 0.74            %2.6
-----------------------------------------------------------------
Efektif katkı = ağırlıkla çarpılmış değerlerin standart sapmasının payı.
Nominal ağırlığından belirgin düşük kalan bir kriter, ölçeğinin tamamını
kullanmadığı için sonuç haritasında beklenenden az ayrım üretiyor demektir.
```

## 3. Risk sınıfları

```
Sınıf Etiket          Üst sınır      Piksel      Pay   Alan (km²)
-----------------------------------------------------------------
1     Çok düşük          0.4131     662,398    %12.9        596.2
2     Düşük              0.4949   1,249,683    %24.3      1,124.7
3     Orta               0.5717   1,512,329    %29.4      1,361.1
4     Yüksek             0.6599   1,160,681    %22.5      1,044.6
5     Çok yüksek         0.8748     564,873    %11.0        508.4
-----------------------------------------------------------------
TOPLAM                            5,149,964   %100.0      4,635.0

Maskeli (yerleşim/su/veri boşluğu): 376,856 piksel, 339.2 km²
```

## 4. Duyarlılık analizi (±%10)

```
Senaryo                       Ort. fark  Maks. fark  Sınıf uyumu  Spearman
--------------------------------------------------------------------------
precipitation_minus10           0.00654     0.01778       %92.38   0.99669
precipitation_plus10            0.00654     0.01778       %92.47   0.99653
irrigation_access_plus10        0.00531     0.01406       %94.15   0.99876
irrigation_access_minus10       0.00531     0.01406       %94.19   0.99877
ndvi_dry_plus10                 0.00373     0.01349       %95.71   0.99893
ndvi_dry_minus10                0.00373     0.01349       %95.73   0.99887
lst_plus10                      0.00277     0.00993       %96.86   0.99943
lst_minus10                     0.00277     0.00993       %96.88   0.99943
soil_awc_minus10                0.00271     0.01136       %96.96   0.99943
soil_awc_plus10                 0.00271     0.01136       %96.97   0.99944
landcover_plus10                0.00228     0.00668       %97.36   0.99966
landcover_minus10               0.00228     0.00668       %97.38   0.99967
distance_to_water_plus10        0.00195     0.00479       %97.84   0.99997
distance_to_water_minus10       0.00195     0.00479       %97.85   0.99997
slope_plus10                    0.00138     0.00382       %98.53   0.99991
slope_minus10                   0.00138     0.00382       %98.53   0.99992
aspect_plus10                   0.00069     0.00212       %99.22   0.99996
aspect_minus10                  0.00069     0.00212       %99.23   0.99996
--------------------------------------------------------------------------
En duyarlı senaryo: precipitation_minus10 — sınıf uyumu %92.38
```