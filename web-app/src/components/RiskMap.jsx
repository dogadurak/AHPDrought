import { useState } from "react";
import { MapContainer, ImageOverlay, LayersControl, TileLayer } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { pct } from "../lib/format";

/**
 * Risk sınıfı haritası.
 *
 * Kaplama, `scripts/export_web_data.py` tarafından sınıf raster'ından
 * üretilir: EPSG:4326'ya yeniden projekte edilmiş, config paletiyle
 * renklendirilmiş, kenarlıksız ve maskeli pikselleri şeffaf bir PNG.
 * Sınırlar da aynı yeniden projeksiyondan gelir, elle yazılmaz.
 *
 * `outputs/figures/risk_map_*.png` BURAYA KONULAMAZ: o bir figürdür (başlık,
 * eksen, lejant, ölçek çubuğu içerir) ve coğrafi sınırlara gerildiğinde
 * raster kayar.
 *
 * İkinci katman (`overlayRf`) Adım 16'nın Random Forest tahminidir. AHP'nin
 * yerine geçmez; katman denetiminden açılıp aynı lejantla karşılaştırılır.
 * İkisinin birbirini tutmaması projenin bulgusudur, kusuru değil.
 */
export function RiskMap({ overlay, overlayRf, classes, dark, fallbackImage }) {
  const [opacity, setOpacity] = useState(0.78);

  if (!overlay) {
    return (
      <div className="map-fallback">
        <img src={fallbackImage} alt="Kuraklık risk haritası (statik figür)" />
        <p className="note">
          Etkileşimli kaplama üretilmemiş. Raster yerelde varken{" "}
          <code>python -m scripts.export_web_data</code> çalıştırıldığında
          etkileşimli harita gelir.
        </p>
      </div>
    );
  }

  const color = (c) => (dark ? c.color_dark : c.color);

  // Esri'nin gri kanvas altlıkları anahtarsız sunuluyor ve tasarım olarak
  // geri planda kalıyor — üstteki risk katmanının rengiyle yarışmıyor.
  // (CartoDB altlıkları artık anahtarsız kullanımda tile'ların üstüne
  // "API KEY REQUIRED" filigranı basıyor, o yüzden kullanılmıyor.)
  const basemap = dark
    ? "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
    : "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}";
  const esriAttribution =
    'Altlık: <a href="https://www.esri.com/">Esri</a> — HERE, Garmin, OpenStreetMap katkıcıları';

  return (
    <div className="map">
      <MapContainer
        bounds={overlay.bounds}
        boundsOptions={{ padding: [12, 12] }}
        // Tam sayı zoom adımları havzayı kadraja sığdırırken büyük boşluk
        // bırakıyor; çeyrek adım sınırlara daha sıkı oturuyor.
        zoomSnap={0.25}
        scrollWheelZoom={false}
        className="map__canvas"
      >
        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Gri kanvas">
            <TileLayer key={basemap} attribution={esriAttribution} url={basemap} />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Uydu görüntüsü">
            <TileLayer
              attribution='Uydu: <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics'
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
            />
          </LayersControl.BaseLayer>
          <LayersControl.Overlay checked name="AHP risk sınıfı">
            <ImageOverlay
              url={overlay.url}
              bounds={overlay.bounds}
              opacity={opacity}
            />
          </LayersControl.Overlay>
          {overlayRf && (
            <LayersControl.Overlay name="Random Forest tahmini">
              <ImageOverlay
                url={overlayRf.url}
                bounds={overlayRf.bounds}
                opacity={opacity}
              />
            </LayersControl.Overlay>
          )}
        </LayersControl>
      </MapContainer>

      <div className="map__legend">
        <h4 className="map__legend-title">Kuraklık risk sınıfı</h4>
        <ul className="map__legend-list">
          {classes.map((c) => (
            <li key={c.class}>
              <span
                className="map__legend-swatch"
                style={{ background: color(c) }}
                aria-hidden="true"
              />
              <span className="map__legend-label">{c.label}</span>
              <span className="map__legend-share num">{pct(c.share_pct)}</span>
            </li>
          ))}
          <li className="map__legend-masked">
            <span className="map__legend-swatch is-empty" aria-hidden="true" />
            <span className="map__legend-label">Maskeli (yerleşim / su)</span>
          </li>
        </ul>

        {overlayRf && (
          <p className="note map__layer-hint">
            Sağ üstteki katman denetiminden <strong>Random Forest tahmini</strong>
            {" "}açılabilir — aynı palet, aynı sınıf sayısı, farklı model.
          </p>
        )}

        <label className="map__opacity">
          <span>Katman opaklığı</span>
          <input
            type="range"
            min="0"
            max="1"
            step="0.02"
            value={opacity}
            onChange={(e) => setOpacity(Number(e.target.value))}
          />
        </label>
      </div>
    </div>
  );
}
