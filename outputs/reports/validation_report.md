# Doğrulama Raporu

**Bölge:** Gediz Havzası — Salihli / Alaşehir / Sarıgöl alt havzası  
**Senaryo:** `steep_riskier`  
**Grid:** EPSG:32635, 30 m

## Kapsam ve sınırlılıklar

Tam bağımsız doğrulama saha verisi gerektirir (TÜİK ilçe bazında verim,
DSİ sulama kayıtları, MGM kuraklık indeksi). Bu kaynakların açık API'si
olmadığından ve manuel indirme projenin "her adım tek başına
çalıştırılabilir" kısıtını kıracağından, bu rapor üç seviyeli ve sınırları
açıkça bildirilen bir doğrulama sunar. Aşağıdaki sonuçlar modelin **iç
tutarlılığını** ve **beklenen fiziksel yönlerle uyumunu** gösterir;
gerçek kuraklık zararıyla doğrulanmış değildir.

## 1. Senaryo dayanıklılığı

Eğimin risk yönü literatürde tartışmalı olduğundan iki senaryo da üretildi.
Sonuç bu tek karara aşırı duyarlıysa harita savunulamaz.

| Karşılaştırma | `steep_riskier` vs `flat_riskier` |
|---|---|
| Risk indeksi ortalama farkı | 0.0335 |
| Risk indeksi maksimum farkı | 0.0594 |
| Aynı sınıfta kalan piksel | %76.2 |
| En fazla 1 sınıf kayan piksel | %100.0 |

## 2. Mevsimsel NDVI genliği (yarı bağımsız)

Genlik = ilkbahar tepe NDVI − yaz dip NDVI. Kriter olarak kullanılan
*kurak dönem NDVI seviyesi*nden farklı bir büyüklüktür, ama aynı
sensörden türediği için kısmi döngüsellik taşır.

**Beklenti:** risk sınıfı arttıkça mevsimsel genlik de artmalı.

| Risk sınıfı | Ortalama mevsimsel NDVI düşüşü | Piksel |
|---|---|---|
| 1 — Çok düşük | 0.0504 | 644,564 |
| 2 — Düşük | 0.0985 | 1,296,807 |
| 3 — Orta | 0.1730 | 1,505,126 |
| 4 — Yüksek | 0.2579 | 1,297,035 |
| 5 — Çok yüksek | 0.3575 | 624,052 |

**Sonuç:** beklenen yönde, monoton artıyor.

## 3. Katmanlı özet

### Arazi örtüsüne göre ortalama risk

| Arazi örtüsü | Ortalama risk | Alan payı |
|---|---|---|
| Bare / sparse vegetation | 0.6346 | %0.6 |
| Grassland | 0.5358 | %25.9 |
| Cropland | 0.5358 | %26.0 |
| Shrubland | 0.5196 | %1.4 |
| Tree cover | 0.4283 | %43.2 |

### Yükseklik kuşağına göre ortalama risk

| Yükseklik | Ortalama risk | Piksel |
|---|---|---|
| 33–128 m | 0.5491 | 1,073,608 |
| 128–293 m | 0.5293 | 1,073,607 |
| 293–554 m | 0.5005 | 1,073,606 |
| 554–849 m | 0.4734 | 1,073,608 |
| 849–2,149 m | 0.3893 | 1,073,608 |

## Gerçek doğrulama için gereken

- TÜİK bitkisel üretim istatistikleri: ilçe bazında bağ/zeytin/pamuk verimi,
  kurak yıllar (2021) ile yaş yıllar (2024) karşılaştırması.
- DSİ Demirköprü sulama şebekesi kayıtları: fiilen sulanan alanların sınırı.
- MGM SPI/SPEI istasyon verisi: meteorolojik kuraklığın bağımsız ölçümü.
- Saha örneklemi: yüksek risk sınıfında rastgele parsellerin yerinde kontrolü.

Bunlar eklendiğinde bu rapor, mevcut iç tutarlılık kontrollerinin yerine
değil, üzerine gelmelidir.