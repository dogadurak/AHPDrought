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
1     Çok düşük          0.3136     763,944    %14.8        687.5
2     Düşük              0.3785   1,331,994    %25.9      1,198.8
3     Orta               0.4416   1,474,636    %28.6      1,327.2
4     Yüksek             0.5168   1,102,676    %21.4        992.4
5     Çok yüksek         0.7211     476,714     %9.3        429.0
-----------------------------------------------------------------
TOPLAM                            5,149,964   %100.0      4,635.0

Maskeli (yerleşim/su/veri boşluğu): 376,856 piksel, 339.2 km²
```

## 4. Duyarlılık analizi (±%10)

```
Senaryo                       Ort. fark  Maks. fark  Sınıf uyumu  Spearman
--------------------------------------------------------------------------
precipitation_minus10           0.00488     0.01326       %93.08   0.99714
precipitation_plus10            0.00488     0.01326       %93.14   0.99707
irrigation_access_plus10        0.00400     0.01225       %94.50   0.99893
irrigation_access_minus10       0.00400     0.01225       %94.55   0.99892
ndvi_dry_minus10                0.00281     0.01109       %96.04   0.99902
ndvi_dry_plus10                 0.00281     0.01109       %96.05   0.99906
lst_minus10                     0.00210     0.00760       %97.05   0.99950
lst_plus10                      0.00210     0.00760       %97.07   0.99949
soil_awc_plus10                 0.00205     0.00891       %97.17   0.99951
soil_awc_minus10                0.00205     0.00891       %97.18   0.99950
landcover_plus10                0.00171     0.00500       %97.62   0.99972
landcover_minus10               0.00171     0.00500       %97.63   0.99973
distance_to_water_plus10        0.00145     0.00335       %97.98   0.99998
distance_to_water_minus10       0.00145     0.00335       %98.02   0.99998
slope_plus10                    0.00104     0.00308       %98.63   0.99992
slope_minus10                   0.00104     0.00308       %98.65   0.99992
aspect_plus10                   0.00052     0.00179       %99.29   0.99997
aspect_minus10                  0.00052     0.00179       %99.29   0.99997
--------------------------------------------------------------------------
En duyarlı senaryo: precipitation_minus10 — sınıf uyumu %93.08
```

## 5. Bağımsız k-means çapraz kontrolü

Jenks doğal kırılımlarıyla üretilen sınıflar, aynı risk indeksine bağımsız olarak uygulanan k-means sınıflandırmasıyla **%99.7** oranında aynı sınıfı veriyor.

Jenks tek boyutlu bir optimizasyon, k-means farklı bir amaç fonksiyonu
kullanır; uyumun yüksek çıkması sınıf sınırlarının yöntem seçiminden
değil verinin kendi yapısından geldiğini gösterir.