# Web vitrini — Gediz Havzası kuraklık riski

Projenin genel okura yönelik arayüzü: etkileşimli risk haritası, AHP
ağırlıkları, sulamanın maskeleme etkisi ve doğrulamanın olumsuz sonucu.
React + Vite, ek çalışma zamanı bağımlılığı yok (harita için Leaflet).

Analist arayüzü ayrı: [`../dashboard/app.py`](../dashboard/app.py) (Streamlit).
**İkisi de aynı veri dosyasını okur**, bu yüzden sayıları hiçbir zaman
birbirinden sapamaz.

## Verinin geldiği yer

```
config.yaml ─┐
             ├─► scripts/export_web_data.py ─► web-app/public/data/
outputs/     │                                   ├── summary.json
  reports/  ─┤                                   └── risk_overlay_<senaryo>.png
data/        │
  processed/─┘
```

Arayüzde **elle yazılmış tek bir sayı yok**. Ağırlıklar projenin kendi AHP
çözücüsünden (`src/ahp.py`), risk sınıfı payları doğrudan risk raster'ından
sayılarak, sulama ve doğrulama tabloları `outputs/reports/` altındaki
raporlardan geliyor.

Analiz yeniden çalıştığında özeti de tazeleyin:

```bash
python -m scripts.export_web_data
python -m scripts.export_web_data --scenario flat_riskier
```

### Harita kaplaması neden ayrıca üretiliyor

`outputs/figures/risk_map_*.png` bir **figürdür** — başlık, eksen, lejant ve
ölçek çubuğu içerir; veri pikselleri görüntünün yalnızca bir bölümünü kaplar.
Onu coğrafi sınırlara germek raster'ı kaydırır ve ölçeğini bozar.

`export_web_data.py` bunun yerine sınıf raster'ının kendisini EPSG:4326'ya
yeniden projekte ediyor (en yakın komşu — sınıf değerleri kategorik), config
paletiyle renklendiriyor, maskeli pikselleri tamamen şeffaf bırakıyor ve
gerçek sınırlarını JSON'a yazıyor.

## Geliştirme

```bash
npm install
npm run dev        # http://localhost:5173
npm run lint
npm run build
npm run preview
```

`public/data/summary.json` yoksa sayfa boş açılmaz; ne yapılması gerektiğini
söyleyen bir hata ekranı gösterir.

## Dağıtım

`main` dalına `web-app/**` altında bir değişiklik gittiğinde
[`.github/workflows/deploy-web.yml`](../.github/workflows/deploy-web.yml)
GitHub Pages'e dağıtır. Proje sitesi alt dizinde sunulduğu için taban yol
derleme sırasında `BASE_PATH` ile veriliyor; bütün varlık referansları
`import.meta.env.BASE_URL` üzerinden çözülüyor.

`public/data/` içeriği repoda tutulur: girdisi olan risk raster'ı repoya
girmediği için CI onu yeniden üretemez.

## Yapı

```
src/
  App.jsx                sayfa kurgusu, tema durumu, veri yükleme
  App.css                düzen ve bileşen stilleri
  index.css              tema belirteçleri (açık/koyu/sistem) ve sıfırlama
  lib/format.js          Türkçe sayı biçimlendirme
  components/
    RiskMap.jsx          Leaflet haritası, kaplama, lejant, opaklık denetimi
    charts.jsx           SVG ve HTML grafikler
    Figure.jsx           grafik sarmalayıcı, grafik/tablo anahtarı, lejant
    modules.jsx          bilgi hiyerarşisi: bulgu, metrik, katlanır panel
public/
  data/                  export_web_data.py çıktısı
  figures/               statik figürler (etkileşimli kaplama yoksa yedek)
```

## Tasarım notları

- **Risk paleti arayüzde seçilmiyor.** `config.yaml`'daki tek-hue ordinal
  rampa JSON üzerinden geliyor; harita, lejant ve dağılım grafiği aynı
  renkleri kullanıyor. Rampa ordinal erişilebilirlik kontrollerinin dördünü
  de geçiyor (açık uç 2,30:1 kontrast, monoton açıklık, tek hue).
- **Kategorik seriler** (nominal ağırlık ↔ efektif katkı, kanala yakın ↔ uzak)
  mavi–turuncu; renk körlüğü ayrımı ΔE 24,7 (protan), her iki temada da
  yüzeye karşı ≥ 3:1.
- **Üç seviyeli bilgi hiyerarşisi.** Her bölümde önce bulgu (`Finding`),
  sonra figür ve sayılar (`Metric`), en sonda gerekçe ve teknik ayrıntı
  (`Disclosure`). Katlanan hiçbir şey silinmez: içerik DOM'da durur, Ctrl+F
  bulup paneli açar, yazdırmada hepsi açılır, çapayla gelen okurda ilgili
  panel açık gelir. Katlanır panelin başlığı bir etiket değil, bulgunun
  kendisidir — panel kapalıyken de sayı ekranda kalsın diye.
  `python -m scripts.check_web_content` hiçbir bulgunun düşmediğini derlenmiş
  paket üzerinden sınar.
- **Sınırlılıklar katlanmaz.** Bir risk haritasının en kolay kötüye
  kullanılacak yeri, sınırları okunmadan haritaya bakılmasıdır; bu yüzden
  Yöntem bölümündeki beş sınırlılık her zaman açık.
- **Her grafiğin tablo görünümü var.** Renk körlüğü, ekran okuyucu ve
  yazdırma durumlarında sayılara ulaşmanın yolu odur.
- **Üç tema durumu:** sistem (varsayılan), açık, koyu. Seçim `localStorage`'da;
  erişilemezse sistem ayarına düşer.
- **Altlık haritası Esri gri kanvas** — anahtarsız ve geri planda kalıyor.
  CartoDB altlıkları anahtarsız kullanımda tile'ların üstüne filigran basıyor.
