# PROJE PROMPT'U — AHP Tabanlı Tarımsal Kuraklık Risk Haritalama Sistemi

Bu dosyayı VS Code'da agent'a (Claude Code / Copilot Agent) doğrudan verebilirsin. Adım adım, doğrulanabilir çıktılar üreterek ilerle.

---

## 1. Proje Tanımı

**Pilot bölge:** Gediz Havzası, Manisa merkezli alt havza (Salihli–Alaşehir–Sarıgöl hattı, Demirköprü Barajı membaı dahil; yaklaşık bbox: 27.6°E–28.6°E, 38.2°N–38.7°N — agent bunu OSM/idari sınır verisiyle kesinleştirecek).

**Neden Gediz Havzası:** Yoğun bağ/zeytin/pamuk tarımı yapılan, düzenli su stresi yaşayan bilinen bir havza; Demirköprü Barajı'nın varlığı sayesinde hem kuraklık hem de (istenirse ileride) sel/taşkın riski analizine genişletilebilir; bağ ve meyve bahçelerinin sonbahar yaprak dökümü/sararması NDVI zaman serisinde net görülür, bu da mevsimsel görselleştirme hedefine (Adım 6) iyi oturuyor; ayrıca CORINE'de tarım-orman-yerleşim çeşitliliği zengin, tek tip arazi örtüsüne sıkışmıyor.

**Amaç:** Eğim, bakı, arazi örtüsü, NDVI zaman serisi ve su kaynağına mesafe değişkenlerini ortak bir grid'e (raster) indirgeyip, Çok Kriterli Karar Verme (AHP – Analytic Hierarchy Process) ile ağırlıklandırarak tarımsal kuraklık risk haritası üretmek. Sonuç, 5 sınıflı (çok düşük → çok yüksek) bir risk raster'ı ve buna eşlik eden bir NDVI zaman serisi animasyonu (mevsimsel bitki örtüsü stresi görselleştirmesi) olacak.

**Neden bu proje değerli:** Sadece bir "harita üretici" değil — karar verme metodolojisi (AHP) + duyarlılık analizi + literatürle doğrulama içeren, akademik olarak savunulabilir bir sistem. Portfolyoda "ben sadece kod yazmadım, bir problem çözdüm ve kararımı gerekçelendirdim" mesajını veriyor.

---

## 2. Kriterler ve Ağırlıklandırma Mantığı

AHP'de 5 ana kriter kullanılacak (agent bunları raster katman olarak üretecek, sonra normalize edip ağırlıklandıracak):

| Kriter | Kaynak veri | Neden kuraklık riskiyle ilişkili |
|---|---|---|
| NDVI (bitki örtüsü sağlığı, kuru dönem ortalaması) | Sentinel-2 L2A | Düşük NDVI = stresli/seyrek bitki örtüsü |
| Eğim (slope) | Copernicus DEM GLO-30 | Düşük eğim + düz ova = yüzey suyu tutma zayıf, buharlaşma yüksek |
| Bakı (aspect) | Copernicus DEM GLO-30 | Güney bakı = daha fazla güneş alımı, daha hızlı nem kaybı |
| Arazi örtüsü/kullanımı | CORINE Land Cover (en güncel yıl) | Tarım arazisi vs. orman vs. çıplak toprak farklı kuraklık duyarlılığı taşır |
| Su kaynağına mesafe | OSM/HydroSHEDS akarsu+göl vektörü → Euclidean distance raster | Su kaynağına uzaklık arttıkça sulama erişimi ve doğal nem azalır |

**AHP adımları (agent bunu ayrı bir Python modülünde uygulayacak, hardcode ağırlık YASAK):**
1. 5x5 ikili karşılaştırma matrisi (pairwise comparison matrix) — başlangıç değerleri literatürden (Saaty ölçeği 1-9) alınacak, kaynak makale referansı kod içinde yorum olarak belirtilecek.
2. Özvektör (eigenvector) yöntemiyle normalize ağırlıkların hesaplanması.
3. Tutarlılık oranı (Consistency Ratio, CR) hesaplanması — CR > 0.10 ise matris otomatik olarak reddedilip hata fırlatılacak.
4. Ağırlıklı çakıştırma (weighted overlay): her kriter raster'ı 0-1 aralığına normalize edilip, AHP ağırlıklarıyla çarpılıp toplanacak.
5. Sonuç raster'ı Jenks Natural Breaks veya eşit aralık yöntemiyle 5 risk sınıfına ayrılacak.

---

## 3. Python Stack ve Kütüphaneler

```
rasterio          # raster okuma/yazma/reprojeksiyon
rasterstats        # zonal statistics (grid hücresi bazlı özetleme)
geopandas          # vektör veri (su kaynakları, idari sınır, CORINE)
numpy              # AHP matris işlemleri, eigenvector hesaplama
scikit-learn        # opsiyonel: risk sınıflarının k-means ile doğrulanması
matplotlib / rioxarray  # görselleştirme ve zaman serisi işleme
sentinelhub veya pystac-client + planetary-computer  # Sentinel-2 erişimi
```

---

## 4. Adım Adım Uygulama Planı (Agent'ın izleyeceği sıra)

### Adım 0 — Proje iskeleti
- `git init`, standart klasör yapısı: `/data/raw`, `/data/processed`, `/src`, `/notebooks`, `/outputs`, `/tests`
- `environment.yml` veya `requirements.txt` oluştur (conda env: `kuraklik_env`, Python 3.10)
- `.gitignore` içine `/data/raw` ve büyük raster dosyaları eklensin (Git LFS kullanılmayacaksa)

### Adım 1 — Çalışma alanı ve grid tanımı
- Pilot bölge bbox'ını AOI (area of interest) olarak GeoJSON şeklinde kaydet
- Ortak grid çözünürlüğünü belirle (öneri: 30m, DEM'in native çözünürlüğüne uydur)
- Tüm katmanların aynı CRS'e (öneri: EPSG:32636, UTM 36N) reprojekte edileceği bir merkezi fonksiyon yaz (`reproject_to_grid()`)

### Adım 2 — Veri indirme modülleri (her biri ayrı, test edilebilir fonksiyon)
- `fetch_dem()` — Copernicus DEM GLO-30, AOI için
- `fetch_sentinel2_ndvi()` — Microsoft Planetary Computer STAC API üzerinden, kuru dönem (Temmuz-Eylül) ve nemli dönem (Mart-Mayıs) için ayrı ayrı bulutsuz kompozit NDVI üret; ayrıca 12 aylık zaman serisi indir (animasyon için)
- `fetch_corine()` — Copernicus Land Monitoring Service CORINE en güncel yıl, AOI'ye kırp
- `fetch_water_features()` — OSM (osmnx) veya HydroSHEDS'ten akarsu/göl vektörü çek

### Adım 3 — Kriter raster'larının üretimi
- Slope ve aspect: `rasterio` + `numpy.gradient` veya `richdem`
- NDVI kompoziti: bulut maskesi (SCL band) uygulanmış medyan kompozit
- CORINE sınıflarını kuraklık duyarlılık skoruna dönüştüren bir lookup tablosu (`corine_susceptibility.json`) — literatürden gerekçelendirilmiş
- Su kaynağına mesafe: `scipy.ndimage.distance_transform_edt` veya `rasterstats` ile Euclidean distance raster

### Adım 4 — AHP modülü (`src/ahp.py`)
- Pairwise comparison matrix sınıfı, eigenvector + CR hesaplama fonksiyonları
- Duyarlılık analizi: ağırlıkları ±%10 değiştirip sonuç haritasının ne kadar değiştiğini gösteren bir fonksiyon (bu kısım akademik ciddiyet katıyor, atlama)

### Adım 5 — Risk haritası üretimi
- Normalize edilmiş kriterlerin ağırlıklı toplamı
- 5 sınıflı risk haritası (Jenks Natural Breaks — `mapclassify` kütüphanesi)
- Çıktı: GeoTIFF + stilize edilmiş PNG/matplotlib harita

### Adım 6 — NDVI zaman serisi görselleştirmesi
- 12 aylık NDVI kompozitlerinden bir animasyon (GIF/MP4, `matplotlib.animation`)
- Pilot bölgedeki birkaç örnek parselin zaman içindeki NDVI eğrisi (çizgi grafik) — "yaprağın ne zaman sarardığını" gösteren bu grafik

### Adım 7 — Doğrulama
- Mümkünse TUİK kuraklık/verim istatistikleri veya literatürdeki mevcut Konya kuraklık haritalarıyla görsel/istatistiksel karşılaştırma
- Karşılaştırma sonucu bir `validation_report.md` olarak yazılsın

### Adım 8 — Testler ve CI
- `pytest` ile her modül için birim test (özellikle AHP matris/CR hesaplama — bunun kesin sonucu olmalı, test edilebilir)
- GitHub Actions ile testlerin otomatik çalışması (`.github/workflows/test.yml`)

### Adım 9 — README ve sunum
- Proje amacı, metodoloji, kullanılan veri kaynakları, örnek çıktılar (harita + animasyon GIF gömülü)
- Kurulum ve çalıştırma talimatları
- "Neden AHP" ve "neden bu pilot bölge" kısa açıklaması

---

## 5. Kısıtlar / Kalite Kriterleri

- Hiçbir ağırlık veya eşik değeri kod içine sabit (magic number) olarak gömülmesin — hepsi config dosyasında (`config.yaml`) veya AHP matrisinden türetilsin
- Her veri kaynağı tamamen açık ve ücretsiz olmalı (API key gerekiyorsa — Planetary Computer gibi — ücretsiz kayıt yeterli olmalı)
- Kod modüler olsun: her adım ayrı, tek başına çalıştırılabilir, test edilebilir bir fonksiyon/script olsun
- Sonuçta çalışan bir GitHub reposu + görsel çıktılar (statik harita + NDVI animasyonu) hedeflenmeli

---

## 6. Agent'a Not

Önce Adım 0 ve Adım 1'i tamamla, bana grid/CRS/AOI kararlarını özetleyip onay için sun. Sonra sırayla Adım 2'den itibaren ilerle — her adımdan sonra kısa bir özet ve varsa ara çıktı görseli paylaş, bir sonraki adıma geçmeden önce.
