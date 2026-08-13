# AHP Kuraklık Risk Analizi — senaryo `steep_riskier`

**Bölge:** Gediz Havzası — Salihli / Alaşehir / Sarıgöl alt havzası  
**Grid:** EPSG:32635, 30 m  
**Referans yılları:** [2019, 2020, 2021, 2022, 2023, 2024]

## 1. AHP ağırlıkları

```
Kriter                   Ağırlık
--------------------------------
precipitation             0.2794
ndvi_dry                  0.2211
lst                       0.1698
landcover                 0.1253
distance_to_water         0.1067
slope                     0.0594
aspect                    0.0385
--------------------------------
TOPLAM                    1.0000

lambda_max = 7.0741   (n = 7)
CI         = 0.0123
RI         = 1.3200
CR         = 0.0094
```

Tutarlılık oranı CR = 0.0094 (eşik 0.1) — matris kabul edildi.

## 2. Nominal ağırlık ve efektif katkı

```
Kriter                Ağırlık   Kullanılan aralık   Efektif katkı
-----------------------------------------------------------------
precipitation          0.2794         0.00 - 1.00           %31.4
ndvi_dry               0.2211         0.00 - 1.00           %22.6
lst                    0.1698         0.00 - 1.00           %16.8
landcover              0.1253         0.10 - 1.00           %13.0
slope                  0.0594         0.00 - 1.00            %6.3
distance_to_water      0.1067         0.00 - 0.80            %5.4
aspect                 0.0385         0.00 - 1.00            %4.5
-----------------------------------------------------------------
Efektif katkı = ağırlıkla çarpılmış değerlerin standart sapmasının payı.
Nominal ağırlığından belirgin düşük kalan bir kriter, ölçeğinin tamamını
kullanmadığı için sonuç haritasında beklenenden az ayrım üretiyor demektir.
```

## 3. Risk sınıfları

```
Sınıf Etiket          Üst sınır      Piksel      Pay   Alan (km²)
-----------------------------------------------------------------
1     Çok düşük          0.3458     644,564    %12.0        580.1
2     Düşük              0.4480   1,296,839    %24.2      1,167.2
3     Orta               0.5338   1,505,219    %28.0      1,354.7
4     Yüksek             0.6304   1,297,226    %24.2      1,167.5
5     Çok yüksek         0.8425     624,189    %11.6        561.8
-----------------------------------------------------------------
TOPLAM                            5,368,037   %100.0      4,831.2

Maskeli (yerleşim/su/veri boşluğu): 158,783 piksel, 142.9 km²
```