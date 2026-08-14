# AHP Kuraklık Risk Analizi — senaryo `steep_riskier`

**Bölge:** Gediz Havzası — Salihli / Alaşehir / Sarıgöl alt havzası  
**Grid:** EPSG:32635, 30 m  
**Referans yılları:** [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

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
precipitation          0.2135         0.00 - 1.00           %24.3
ndvi_dry               0.1585         0.00 - 1.00           %16.5
irrigation_access      0.1782         0.00 - 1.00           %16.1
soil_awc               0.1336         0.00 - 1.00           %12.2
lst                    0.1117         0.00 - 1.00           %11.5
landcover              0.0843         0.10 - 1.00            %9.0
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
1     Çok düşük          0.4163     669,824    %13.0        602.8
2     Düşük              0.4985   1,277,281    %24.8      1,149.6
3     Orta               0.5756   1,524,569    %29.6      1,372.1
4     Yüksek             0.6642   1,149,239    %22.3      1,034.3
5     Çok yüksek         0.8749     529,051    %10.3        476.1
-----------------------------------------------------------------
TOPLAM                            5,149,964   %100.0      4,635.0

Maskeli (yerleşim/su/veri boşluğu): 376,856 piksel, 339.2 km²
```