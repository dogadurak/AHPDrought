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
| Risk indeksi ortalama farkı | 0.0178 |
| Risk indeksi maksimum farkı | 0.0383 |
| Aynı sınıfta kalan piksel | %79.4 |
| En fazla 1 sınıf kayan piksel | %100.0 |

## 2. Buharlaşma oranı ET/PET (BAĞIMSIZ)

MODIS MOD16A3GF yıllık evapotranspirasyon ürününden ET/PET oranı.
Bu, modele hiç girmemiş bir ölçümdür: ayrı bir Penman-Monteith
modelinden üretilir ve bu projedeki hiçbir kriter (CHIRPS yağış,
Sentinel-2 NDVI, MODIS LST, WorldCover, SoilGrids, OSM mesafeleri)
onun girdisi değildir. Tek dolaylı bağ MOD16'nın MODIS LAI/FPAR
kullanmasıdır, yani bitki örtüsüyle akrabalığı sıfır değildir.

**Beklenti:** risk sınıfı arttıkça ET/PET AZALMALI (su kısıtı artar).

| Risk sınıfı | Ortalama ET/PET | Piksel |
|---|---|---|
| 1 — Çok düşük | 0.2770 | 737,698 |
| 2 — Düşük | 0.2682 | 1,296,831 |
| 3 — Orta | 0.2558 | 1,455,183 |
| 4 — Yüksek | 0.2374 | 1,088,243 |
| 5 — Çok yüksek | 0.2347 | 464,630 |

Risk indeksi ile ET/PET arasında Spearman ρ = **-0.2833**.
**Sonuç:** beklenen yönde, monoton azalıyor.

## 3. Mevsimsel NDVI genliği (yarı bağımsız)

Genlik = ilkbahar tepe NDVI − yaz dip NDVI. Kriter olarak kullanılan
*kurak dönem NDVI seviyesi*nden farklı bir büyüklüktür, ama aynı
sensörden türediği için kısmi döngüsellik taşır.

**Beklenti:** risk sınıfı arttıkça mevsimsel genlik de artmalı.

| Risk sınıfı | Ortalama mevsimsel NDVI düşüşü | Piksel |
|---|---|---|
| 1 — Çok düşük | 0.0532 | 763,944 |
| 2 — Düşük | 0.1299 | 1,331,994 |
| 3 — Orta | 0.1826 | 1,474,633 |
| 4 — Yüksek | 0.2552 | 1,102,609 |
| 5 — Çok yüksek | 0.3265 | 476,332 |

**Sonuç:** beklenen yönde, monoton artıyor.

## 4. Katmanlı özet

### Arazi örtüsüne göre ortalama risk

| Arazi örtüsü | Ortalama risk | Alan payı |
|---|---|---|
| Bare / sparse vegetation | 0.4582 | %0.6 |
| Grassland | 0.4386 | %24.8 |
| Shrubland | 0.4299 | %1.3 |
| Cropland | 0.3951 | %24.3 |
| Tree cover | 0.3829 | %42.2 |

### Yükseklik kuşağına göre ortalama risk

| Yükseklik | Ortalama risk | Piksel |
|---|---|---|
| 33–132 m | 0.3853 | 1,029,991 |
| 132–302 m | 0.4092 | 1,029,995 |
| 302–563 m | 0.4193 | 1,029,992 |
| 563–860 m | 0.4216 | 1,029,993 |
| 860–2,149 m | 0.3747 | 1,029,993 |

## Gerçek doğrulama için gereken

- TÜİK bitkisel üretim istatistikleri: ilçe bazında bağ/zeytin/pamuk verimi,
  kurak yıllar (2021) ile yaş yıllar (2024) karşılaştırması.
- DSİ Demirköprü sulama şebekesi kayıtları: fiilen sulanan alanların sınırı.
- MGM SPI/SPEI istasyon verisi: meteorolojik kuraklığın bağımsız ölçümü.
- Saha örneklemi: yüksek risk sınıfında rastgele parsellerin yerinde kontrolü.

Bunlar eklendiğinde bu rapor, mevcut iç tutarlılık kontrollerinin yerine
değil, üzerine gelmelidir.