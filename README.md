# AHP Tabanlı Tarımsal Kuraklık Risk Haritalama — Gediz Havzası

Çok Kriterli Karar Verme (AHP) ile üretilen 5 sınıflı tarımsal kuraklık risk
haritası ve buna eşlik eden NDVI zaman serisi görselleştirmesi.

**Pilot bölge:** Gediz Havzası, Manisa — Salihli / Alaşehir / Sarıgöl hattı
(Demirköprü Barajı membaı dahil), yaklaşık 27.6°E–28.6°E, 38.2°N–38.7°N.

> **Durum:** Geliştirme aşamasında. Adım 0 (iskelet) ve Adım 1 (AOI + ortak grid
> + AHP tutarlılık doğrulaması) tamamlandı. Veri indirme modülleri (Adım 2)
> sırada.

---

## Yöntem özeti

Yedi kriter ortak bir 30 m grid'e indirgenir, 0–1 aralığına normalize edilir ve
AHP ile türetilmiş ağırlıklarla çakıştırılır:

| Kriter | Kaynak | Risk yönü |
|---|---|---|
| Kurak dönem yağışı | CHIRPS v2.0 (aylık, ~5.5 km) | Az yağış → yüksek risk |
| Kurak dönem NDVI | Sentinel-2 L2A (medyan kompozit) | Düşük NDVI → yüksek risk |
| Yüzey sıcaklığı (LST) | MODIS MOD11A2 (8 günlük, 1 km) | Yüksek LST → yüksek risk |
| Arazi örtüsü duyarlılığı | ESA WorldCover 2021 (10 m) | Lookup tablosu (0–1) |
| Su kaynağına mesafe | OSM akarsu/göl → Öklid mesafe | Uzak → yüksek risk |
| Eğim | Copernicus DEM GLO-30 | Senaryoya bağlı (aşağıya bkz.) |
| Bakı (southness) | Copernicus DEM GLO-30 | Güney bakı → yüksek risk |

Ağırlıklar **hiçbir yerde sabit değildir**: `config.yaml` içindeki 7×7 ikili
karşılaştırma matrisinden özvektör yöntemiyle türetilir ve tutarlılık oranı
CR > 0.10 ise pipeline hata fırlatarak durur.

### Metodolojik notlar

- **Bakı dairesel bir değişkendir.** 0–360° doğrudan normalize edilemez
  (359° ile 1° komşudur ama uçlara düşer). Bu yüzden
  `southness = (1 − cos(bakı)) / 2` ile skalarlaştırılır: kuzey → 0, güney → 1.
  Eğimin ~0 olduğu düz alanlarda bakı tanımsızdır ve nötr değer (0.5) atanır.
- **Eğimin risk yönü tartışmalıdır.** Literatürdeki yaygın gerekçe "dik yamaç →
  hızlı yüzey akışı → düşük infiltrasyon" yönündedir; alternatif görüş "düz ova
  → zayıf drenaj → yüksek buharlaşma" der. Proje bu tercihi gizlemek yerine iki
  senaryoyu da üretir (`scenarios.steep_riskier` / `scenarios.flat_riskier`) ve
  farkı duyarlılık analizinde raporlar.
- **Ölçek uyumsuzluğu açıkça kabul edilmiştir.** CHIRPS (~5.5 km) ve MODIS LST
  (1 km) katmanları 30 m grid'e yeniden örneklenir. Bu, bu katmanların *yerel*
  değil *bölgesel* gradyan bilgisi taşıdığı anlamına gelir; sonuçlar 30 m
  hassasiyetinde yorumlanmamalıdır. Sınırlılıklar bölümünde raporlanacaktır.
- **NDVI hem girdi hem görselleştirme ekseni.** Bu döngüselliği azaltmak için
  doğrulama (Adım 7) NDVI'dan bağımsız kaynaklarla yapılır (TÜİK verim
  istatistikleri / literatürdeki mevcut kuraklık haritaları).

---

## Kurulum

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux / macOS
pip install -r requirements.txt
```

Python 3.13 ile test edilmiştir. Hiçbir veri kaynağı API anahtarı gerektirmez.

> **Not — PROJ çakışması.** Makinede PostgreSQL/PostGIS, QGIS veya OSGeo4W gibi
> başka bir GDAL dağıtımı kuruluysa, bunlar `PROJ_LIB` / `GDAL_DATA` ortam
> değişkenlerini sistem genelinde kendi (çoğu zaman eski) `proj.db` dosyalarına
> ayarlar ve rasterio hiçbir EPSG kodunu çözemez
> (`DATABASE.LAYOUT.VERSION.MINOR = 2 whereas a number >= 6 is expected`).
> `src/_geoenv.py` bu değişkenleri içe aktarma anında sanal ortamın gömülü PROJ
> kopyasına yönlendirerek sorunu otomatik çözer; sistem değişkenlerine
> dokunulmaz. Devre dışı bırakmak için `AHP_KEEP_SYSTEM_PROJ=1`.

## Çalıştırma

```bash
# Adım 1 — AOI, ortak grid ve AHP tutarlılık kontrolü
python -m scripts.step01_define_grid

# Alternatif eğim senaryosu ile
python -m scripts.step01_define_grid --scenario flat_riskier

# Testler
pytest
```

## Proje yapısı

```
config.yaml                  Tüm ağırlıklar, eşikler ve veri kaynağı ayarları
lookups/                     Kategorik → skor dönüşüm tabloları (WorldCover)
src/
  config.py                  Konfigürasyon yükleme + doğrulama + senaryolar
  grid.py                    Ortak grid tanımı, reproject_to_grid(), G/Ç
  aoi.py                     Çalışma alanı (bbox veya OSM idari sınır)
  ahp.py                     Özvektör, tutarlılık oranı, duyarlılık analizi
scripts/                     Adım adım çalıştırılabilir betikler
tests/                       pytest birim testleri
data/{raw,interim,processed} Veri (git'e girmez)
outputs/{figures,reports}    Harita, animasyon ve raporlar
docs/references.md           Literatür künyeleri
```

## Yol haritası

- [x] **Adım 0** — Proje iskeleti, bağımlılıklar, config mimarisi
- [x] **Adım 1** — AOI, ortak grid (EPSG:32635 / 30 m), AHP tutarlılık doğrulaması
- [ ] **Adım 2** — Veri indirme modülleri (DEM, Sentinel-2, WorldCover, CHIRPS, MODIS LST, OSM su)
- [ ] **Adım 3** — Kriter raster'larının üretimi ve normalizasyonu
- [ ] **Adım 4** — AHP ağırlıklı çakıştırma + duyarlılık analizi
- [ ] **Adım 5** — 5 sınıflı risk haritası (Jenks) + stilize çıktı
- [ ] **Adım 6** — 12 aylık NDVI animasyonu + örnek parsel eğrileri
- [ ] **Adım 7** — Doğrulama raporu
- [ ] **Adım 8** — CI
- [ ] **Adım 9** — Sunum ve literatür künyeleri

## Veri kaynakları

| Veri | Sağlayıcı | Erişim |
|---|---|---|
| Copernicus DEM GLO-30 | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| Sentinel-2 L2A | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| ESA WorldCover 2021 | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| MODIS MOD11A2 (LST) | Microsoft Planetary Computer (STAC) | Açık, anahtarsız |
| CHIRPS v2.0 | Climate Hazards Center, UCSB | Açık HTTP |
| Akarsu / göl vektörü | OpenStreetMap (osmnx) | Açık, ODbL |
