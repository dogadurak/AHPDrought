# AHP Tabanlı Tarımsal Kuraklık Risk Haritalama — Gediz Havzası

Çok Kriterli Karar Verme (AHP) ile üretilen 5 sınıflı tarımsal kuraklık risk
haritası, duyarlılık analizi ve NDVI zaman serisi görselleştirmesi.

**Pilot bölge:** Gediz Havzası, Manisa — Salihli / Alaşehir / Sarıgöl hattı
(Demirköprü Barajı membaı dahil), 27.6°E–28.6°E, 38.2°N–38.7°N → **4.842 km²**,
30 m çözünürlükte 5,53 milyon hücre.

![Kuraklık risk haritası](outputs/figures/risk_map_steep_riskier.png)

---

## Sonuçlar

**AHP ağırlıkları** — 7×7 ikili karşılaştırma matrisinden özvektör yöntemiyle
türetildi, tutarlılık oranı **CR = 0.0094** (eşik 0.10):

| Kriter | Ağırlık | Kaynak |
|---|---:|---|
| Kurak dönem yağışı | 0.279 | CHIRPS v2.0 (~5,5 km) |
| Kurak dönem NDVI | 0.221 | Sentinel-2 L2A (10 m) |
| Yüzey sıcaklığı (LST) | 0.170 | MODIS MYD11A2 (1 km) |
| Arazi örtüsü duyarlılığı | 0.125 | ESA WorldCover 2021 (10 m) |
| Su kaynağına mesafe | 0.107 | OpenStreetMap |
| Eğim | 0.059 | Copernicus DEM GLO-30 |
| Bakı (güneylilik) | 0.038 | Copernicus DEM GLO-30 |

**Risk sınıfları** (Jenks Natural Breaks):

| Sınıf | Alan | Pay |
|---|---:|---:|
| Çok düşük | 580 km² | %12,0 |
| Düşük | 1.167 km² | %24,2 |
| Orta | 1.355 km² | %28,0 |
| Yüksek | 1.168 km² | %24,2 |
| Çok yüksek | 562 km² | %11,6 |

Bağımsız k-means sınıflandırmasıyla **%95,0 uyum** — sınıflar yöntem seçimine
değil verinin kendi yapısına dayanıyor.

### Nominal ağırlık ≠ efektif katkı

AHP ağırlığı, kriterin ölçeğinin tamamını kullandığı varsayımıyla anlam taşır.
Gerçekte:

| Kriter | Ağırlık | Kullanılan aralık | Efektif katkı |
|---|---:|---|---:|
| precipitation | 0,279 | 0,00–1,00 | %31,4 |
| ndvi_dry | 0,221 | 0,00–1,00 | %22,6 |
| lst | 0,170 | 0,00–1,00 | %16,8 |
| landcover | 0,125 | 0,10–1,00 | %13,0 |
| slope | 0,059 | 0,00–1,00 | %6,3 |
| **distance_to_water** | **0,107** | **0,00–0,80** | **%5,4** |
| aspect | 0,038 | 0,00–1,00 | %4,5 |

Su mesafesi kriteri nominal ağırlığının yarısı kadar ayrım üretiyor: 750 km'lik
akarsu ağı sayesinde alanın %90'ı suya 5,6 km'den yakın, dolayısıyla skorlar
0–0,37 bandına sıkışıyor. Bu havzanın gerçeği, bir hata değil — ama ağırlık
tablosuna bakıp "su erişimi haritanın onda birini belirliyor" demek yanlış
olurdu.

### Duyarlılık analizi

Her ağırlık ±%10 değiştirildiğinde 5 sınıflı haritada aynı sınıfta kalan piksel
oranı **en kötü %90,7** (yağış +%10), en iyi %99,0 (bakı). Spearman sıra
korelasyonu hiçbir senaryoda 0,994'ün altına düşmüyor. Harita ağırlık
seçimlerine karşı dayanıklı.

---

## NDVI zaman serisi

![NDVI animasyonu](outputs/figures/ndvi_animation_2024.gif)

![Parsel eğrileri](outputs/figures/ndvi_parcel_curves_2024.png)

Bu grafik havzanın tarımsal karakterini tek bakışta anlatıyor:

- **Tarım alanı** temmuzda zirve yapıyor (0,51), nisan–mayısta dipte (0,36).
  Bu, yağışa değil **sulamaya** dayalı bir tarım demek — Demirköprü'den beslenen
  pamuk ve bağ, yazın en yeşil olduğu dönemi yaşıyor.
- **Mera** tam tersi: nisanda zirve (0,46), ağustosta dip (0,27) — klasik
  Akdeniz yağış rejimi.
- **Orman** yıl boyu düz (0,62–0,68) — derin kök, mevsimsel strese kapalı.

Sayısal tablo: [`outputs/figures/ndvi_parcel_curves_2024.md`](outputs/figures/ndvi_parcel_curves_2024.md)

---

## Kriter katmanları

![Kriter paneli](outputs/figures/criteria_panel_steep_riskier.png)

![Risk indeksi dağılımı](outputs/figures/risk_histogram_steep_riskier.png)

---

## Doğrulama

Tam bağımsız doğrulama saha verisi gerektirir (TÜİK verim istatistikleri, DSİ
sulama kayıtları, MGM kuraklık indeksi) — bu kaynakların açık API'si yok. Bu
yüzden [`validation_report.md`](outputs/reports/validation_report.md) üç
seviyeli ve sınırlarını açıkça bildiren bir doğrulama sunuyor:

**1. Senaryo dayanıklılığı** — eğimin risk yönü literatürde tartışmalı olduğu
için iki senaryo da üretiliyor. Sonuç: piksellerin **%76,2'si aynı sınıfta**,
**%100'ü en fazla 1 sınıf** kayıyor. Tartışmalı karar sonucu değiştiriyor ama
altüst etmiyor.

**2. Mevsimsel NDVI genliği (yarı bağımsız)** — ilkbahar tepe NDVI ile yaz dip
NDVI arasındaki fark, kriter olarak kullanılan *NDVI seviyesinden* farklı bir
büyüklük. Beklenti: risk sınıfı arttıkça genlik artmalı.

| Risk sınıfı | Ortalama mevsimsel NDVI düşüşü |
|---|---:|
| Çok düşük | 0,050 |
| Düşük | 0,099 |
| Orta | 0,173 |
| Yüksek | 0,258 |
| Çok yüksek | 0,358 |

Monoton artıyor — model, bitki örtüsünün yaz boyunca ne kadar kaybedeceğini
doğru sıralıyor. (Aynı sensörden türediği için kısmi döngüsellik taşır.)

**3. Katmanlı özet** — arazi örtüsüne göre risk: çıplak toprak (0,635) > mera =
tarım (0,536) > çalılık (0,520) > orman (0,428). Yüksekliğe göre: 33–128 m
kuşağı 0,549, 849–2149 m kuşağı 0,389. İkisi de beklenen yönde.

---

## Yöntem notları

- **Bakı dairesel bir değişkendir.** 0–360° doğrudan normalize edilemez (359° ile
  1° komşudur ama ölçeğin iki ucuna düşer). `southness = (1 − cos θ) / 2` ile
  skalarlaştırılıyor: kuzey → 0, güney → 1. Eğimin 1°'nin altında olduğu düz
  alanlarda bakı tanımsız kabul edilip nötr değer (0,5) atanıyor.
- **Eğimin risk yönü tartışmalı.** "Dik yamaç → hızlı yüzey akışı → düşük
  infiltrasyon" ile "düz ova → zayıf drenaj → yüksek buharlaşma" görüşleri
  çatışıyor. Proje tercihi gizlemek yerine iki senaryoyu da üretiyor
  (`scenarios.steep_riskier` / `flat_riskier`) ve farkı raporluyor.
- **Maske yayılımı.** Kriterlerden biri bir pikselde tanımsızsa (yerleşim, su
  yüzeyi) o piksel sonuçta da tanımsız kalıyor. Eksik kriteri sıfır saymak
  pikseli yapay olarak "düşük riskli" gösterirdi. Alanın %2,9'u maskeli.
- **Ölçek uyumsuzluğu.** CHIRPS (~5,5 km) ve MODIS LST (1 km) katmanları 30 m
  grid'e yeniden örnekleniyor. Bu katmanlar *bölgesel* gradyan taşır, yerel
  detay değil; sonuçlar 30 m hassasiyetinde yorumlanmamalı.
- **Kısmi döngüsellik.** NDVI hem girdi kriteri hem de görselleştirme ekseni.
  Doğrulama bu yüzden NDVI *seviyesi* yerine *mevsimsel genliği* kullanıyor,
  ama tam bağımsızlık ancak saha verisiyle sağlanır.
- **Renk paleti gerekçelendirildi.** Risk sınıfları ordinal olduğundan tek hue
  üzerinde monoton açıklık adımları kullanılıyor. Yaygın mavi–sarı–kırmızı
  gökkuşağı paleti erişilebilirlik kontrollerinin 4'ünden 3'ünde kalıyordu
  (açıklık monoton değil, tek hue değil, sarı orta sınıf beyaz zeminde
  1,01:1 kontrastla kayboluyor).

---

## Yol boyunca bulunan ve düzeltilen veri hataları

Bu bölüm projenin en öğretici kısmı — hiçbiri hata vermeden, sessizce yanlış
sonuç üretecekti:

**1. Sentinel-2 baseline 04.00 radyometrik offset'i.** 25 Ocak 2022'den itibaren
tüm L2A bantlarına `BOA_ADD_OFFSET = −1000` uygulanıyor ve Planetary Computer
veriyi düzeltmeden sunuyor. Bu AOI'de ölçülen etki (Ağustos, bulut <%10):

| Yıl | baseline | B04 | B08 | NDVI (ham) | NDVI (düzeltilmiş) |
|---|---|---:|---:|---:|---:|
| 2019 | 02.12 | 1180 | 2859 | 0,416 | — |
| 2021 | 03.00 | 1232 | 2869 | 0,399 | — |
| 2022 | 04.00 | 2103 | 3712 | 0,277 | **0,422** |
| 2024 | 05.11 | 2245 | 3873 | 0,266 | **0,395** |

Düzeltilmeden 2022 sonrası yıllar sistematik olarak ~0,13 düşük NDVI veriyordu.
Kuraklık haritasında bu, "son yıllarda bitki örtüsü stresi arttı" diye
okunacaktı — üstelik NDVI 0,221 ağırlıkla ikinci en önemli kriter. Düzeltme
item bazında, `s2:processing_baseline` özelliğine göre uygulanıyor.

**2. Yanlış UTM zone.** Başlangıçta EPSG:32636 (UTM 36N) yazılmıştı; bu zone
30°E'den başlıyor, AOI ise 27,6–28,6°E. Bölge tamamen zone dışında kalıyor ve
ciddi ölçek deformasyonu üretiyordu. Doğrusu **EPSG:32635**.

**3. MODIS koleksiyonu iki platformu karıştırıyor.** `modis-11A2-061` hem Terra
(MOD11A2, ~10:30 geçiş) hem Aqua (MYD11A2, ~13:30) ürünlerini içeriyor ve
item'ların `platform` özelliği boş geliyor — ayrım yalnızca id ön ekinden
yapılabiliyor. Karıştırmak geçiş saati farkı yüzünden birkaç K sistematik sapma
demek. Aqua'ya sabitlendi.

**4. Senaryo kriterleri aynı dosyayı paylaşıyordu.** `slope.tif` her iki
senaryoda da aynı yola yazılıyordu; `flat_riskier` sessizce `steep_riskier`ın
katmanını okuyor, iki senaryo aynı çıkıyor ve senaryo karşılaştırması anlamsız
bir %100 uyum raporluyordu. Senaryoya bağlı kriterler artık dosya adında senaryo
etiketi taşıyor.

**5. Jenks sınıflandırması tekrarlanabilir değildi.** `mapclassify.NaturalBreaks`
küme başlangıçlarını global numpy RNG'sinden çekiyor; tohumlanmadığı için aynı
veriyle iki çalıştırma farklı sınıf sınırları veriyordu (~0,009 indeks birimi —
sınıf sınırlarını kaydırmaya yeter).

**6. PROJ çakışması.** Geliştirme makinesindeki PostgreSQL/PostGIS kurulumu
`PROJ_LIB` ve `GDAL_DATA` değişkenlerini sistem genelinde kendi eski PROJ
veritabanına ayarlamış; rasterio hiçbir EPSG kodunu çözemiyordu.
[`src/_geoenv.py`](src/_geoenv.py) içe aktarma anında sanal ortamın gömülü PROJ
kopyasına yönlendiriyor.

---

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

Python 3.13 ile test edilmiştir. **Hiçbir veri kaynağı API anahtarı
gerektirmez.**

> **PROJ çakışması.** Makinede PostgreSQL/PostGIS, QGIS veya OSGeo4W kuruluysa
> bunlar `PROJ_LIB` / `GDAL_DATA` değişkenlerini sistem genelinde kendi
> `proj.db` dosyalarına ayarlar ve rasterio hiçbir EPSG kodunu çözemez
> (`DATABASE.LAYOUT.VERSION.MINOR = 2 whereas a number >= 6 is expected`).
> `src/_geoenv.py` bunu içe aktarma anında otomatik düzeltir; sistem
> değişkenlerine dokunmaz. Devre dışı bırakmak için `AHP_KEEP_SYSTEM_PROJ=1`.

## Çalıştırma

```bash
# Adım 1 — AOI, ortak grid, AHP tutarlılık kontrolü
python -m scripts.step01_define_grid

# Adım 2 — Veri indirme (~1,5 saat, önbellekli ve kesintiye dayanıklı)
python -m scripts.step02_fetch_data --list      # katmanlar ve süreleri
python -m scripts.step02_fetch_data
python -m scripts.step02_fetch_data --only dem,water --overwrite

# Adım 3 — Kriter raster'ları
python -m scripts.step03_build_criteria
python -m scripts.step03_build_criteria --scenario flat_riskier --only slope

# Adım 4-5 — AHP çakıştırma, duyarlılık, risk haritası
python -m scripts.step04_risk_map

# Adım 6 — NDVI animasyonu ve parsel eğrileri
python -m scripts.step06_ndvi_timeseries

# Adım 7 — Doğrulama raporu
python -m scripts.step07_validate

# Testler
pytest
```

Her katman `data/interim/` altına yazılır ve dosya varsa atlanır; uzun süren
Sentinel-2 işi kesilse bile aynı komut kaldığı yerden devam eder.

## Proje yapısı

```
config.yaml                  Tüm ağırlıklar, eşikler, veri kaynakları, renkler
lookups/                     Kategorik → skor dönüşüm tabloları
src/
  config.py                  Yükleme, doğrulama, senaryolar, kriter yolları
  grid.py                    Ortak grid, reproject_to_grid(), hizalı G/Ç
  aoi.py                     Çalışma alanı
  ahp.py                     Özvektör, tutarlılık oranı, duyarlılık ağırlıkları
  fetch/                     Adım 2 — kaynak başına bir modül
  criteria/                  Adım 3 — eğim/bakı, mesafe, lookup, normalizasyon
  overlay.py                 Adım 4 — ağırlıklı çakıştırma, efektif katkı
  classify.py                Adım 5 — Jenks, k-means çapraz kontrolü
  visualize.py               Adım 5 — harita, panel, histogram
  animate.py                 Adım 6 — GIF ve parsel eğrileri
  validate.py                Adım 7 — üç seviyeli doğrulama
scripts/                     Adım adım çalıştırılabilir betikler
tests/                       153 pytest testi
outputs/{figures,reports}    Harita, animasyon, raporlar
docs/references.md           Literatür künyeleri
```

**Hiçbir ağırlık, eşik, sınıf skoru veya renk kod içine gömülü değildir** —
hepsi `config.yaml` veya `lookups/` içinden gelir. `config.yaml`'ı bozan her
değişiklik (matris boyutu, eksik kriter, ters bbox, sınıf/renk sayısı
uyuşmazlığı) kod çalışmadan anlaşılır bir hata verir.

## Veri kaynakları

| Veri | Sağlayıcı | Erişim |
|---|---|---|
| Copernicus DEM GLO-30 | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| Sentinel-2 L2A | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| ESA WorldCover 2021 | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| MODIS MYD11A2 (LST) | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| CHIRPS v2.0 | Climate Hazards Center, UCSB | Açık HTTP |
| Akarsu / göl vektörü | OpenStreetMap (osmnx) | Açık, ODbL |

Tam künyeler ve ağırlıkların literatür dayanağı:
[`docs/references.md`](docs/references.md)

## Ağırlıkların literatürle karşılaştırması

| Kriter | Bu proje | Pandey & Srivastava (2019) | Sarkar ve ark. (2024)* |
|---|---:|---:|---:|
| Yağış | 0,279 | 0,445 | — |
| NDVI | 0,221 | 0,050 | 0,127 |
| LST | 0,170 | 0,158 | — |
| Arazi örtüsü | 0,125 | — | 0,164 |
| Toprak nemi | — | 0,252 | — |
| Sulama yöntemi | — | — | 0,187 |
| Ekim yoğunluğu | — | — | 0,237 |

\* tarımsal kuraklık bileşeni, bildirilen CR = %5,8

İki karşılaştırma da bu projenin bilinen eksiklerini gösteriyor: **toprak nemi**
ve özellikle **sulama katmanı** yok. Sarkar ve ark. sulamaya 0,187 ağırlık
veriyor — Gediz'de tarımın sulamaya dayalı olduğu parsel eğrilerinden açıkça
görüldüğü için bu en önemli eksik kriter. Açık veriyle elde edilemedi ve
[`docs/references.md`](docs/references.md) içinde kapatılmamış boşluk olarak
kayıt altına alındı.

## Sınırlılıklar — kısa liste

1. **Sulama ve toprak nemi katmanı yok.** Literatürdeki karşılaştırmalarda bu
   ikisi toplam ağırlığın üçte birine kadar çıkıyor.
2. **Bağımsız saha doğrulaması yapılmadı.** TÜİK/DSİ/MGM verilerinin açık API'si
   yok; mevcut doğrulama iç tutarlılık + yarı bağımsız sinyalle sınırlı.
3. **İkili karşılaştırma matrisi uzman anketiyle kurulmadı** — literatürdeki
   sıralamayı temsil eden bir başlangıç seti.
4. **Ölçek uyumsuzluğu:** yağış ~5,5 km, LST 1 km katmanları 30 m grid'e
   yeniden örnekleniyor.
5. **NDVI kısmen döngüsel:** hem girdi kriteri hem doğrulama ekseni.
   EVI'ye geçiş ölçülebilir bir iyileşme sağlayabilir (Jia ve ark. 2020).
