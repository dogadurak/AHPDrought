"""Adım 16 — Random Forest tabanlı risk haritası (AHP haritasının karşılaştırması).

Adım 14'te eğitilen RF modeliyle NDVI anomalisi tahmin edilir; risk, beklenen
hasarın tersi olarak 0-1 arasına ölçeklenip 5 sınıfa ayrılır.

Bu harita AHP haritasının YERİNE GEÇMEZ, yanında durur. İkisi farklı soruları
yanıtlıyor: AHP "fiziksel duyarlılık nerede yüksek", RF "gözlenen stres nerede
yüksek çıkıyor". Projenin asıl bulgusu zaten ikisinin birbirini tutmaması.

ÇIKTI ADLARI BİLEREK AYRI (`*_rf_*`): bu betik bir kez AHP çıktılarının üstüne
yazdı ve site AHP haritası sanarak RF haritasını gösterdi. Bir daha olmasın.

Kullanım:
    python -m scripts.step16_rf_risk_map
    python -m scripts.step16_rf_risk_map --scenario steep_riskier --spi -2.0

Çıktılar:
    data/processed/risk_index_rf_<senaryo>.tif    sürekli indeks (0-1)
    data/processed/risk_class_rf_<senaryo>.tif    5 sınıflı risk (1-5)
"""

from __future__ import annotations

import argparse
import joblib
import numpy as np

from src.classify import class_summary, classify_risk, kmeans_crosscheck
from src.config import load_config
from src.fetch.common import resolve
from src.grid import build_grid, write_raster
from src.overlay import load_criteria

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RF risk haritası (Adım 16)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--spi", type=float, default=-2.0, help="Drought severity scenario (SPI-12)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 16 — RANDOM FOREST RİSK HARİTASI (AHP ile karşılaştırma)")
    print(f"Senaryo: {args.scenario} (SPI: {args.spi})")
    print("=" * 68)

    model_path = resolve(config["paths"]["data_processed"]) / "rf_drought_model.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model bulunamadi: {model_path}. Once step14'u calistirin.")

    print("\n[1] Veri ve Model Yükleniyor...")
    rf = joblib.load(model_path)
    stack = load_criteria(config, grid)
    
    y_coords, x_coords = np.mgrid[0:grid.height, 0:grid.width]
    
    valid = stack.valid_mask
    features = stack.data[:, valid].T

    feature_names_full = list(stack.names)
    if 'ndvi_dry' in feature_names_full:
        ndvi_idx = feature_names_full.index('ndvi_dry')
        features = np.delete(features, ndvi_idx, axis=1)

    f_x = x_coords[valid].reshape(-1, 1)
    f_y = y_coords[valid].reshape(-1, 1)
    f_spi = np.full((features.shape[0], 1), args.spi)
    
    features_extended = np.hstack([features, f_x, f_y, f_spi])
    
    print("\n[2] Risk Tahmini (Inference) Yapılıyor...")
    # Chunked prediction to avoid memory issues
    chunk_size = 500_000
    preds = np.zeros(features_extended.shape[0], dtype="float32")
    for i in range(0, features_extended.shape[0], chunk_size):
        preds[i:i+chunk_size] = rf.predict(features_extended[i:i+chunk_size])
        print(f"  %{(i + chunk_size) / features_extended.shape[0] * 100:.1f} tamamlandi", end="\r")
    
    # NDVI anomalisi negatifse hasar buyuktur.
    # Risk indeksi 0-1 arasinda olmali (1 = en yuksek risk).
    # O yuzden anomalileri tersine cevirip (ne kadar negatif o kadar riskli), MinMax ile 0-1 yapiyoruz.
    risk_raw = -preds
    risk_min, risk_max = risk_raw.min(), risk_raw.max()
    risk_normalized = (risk_raw - risk_min) / (risk_max - risk_min + 1e-9)
    
    risk_map = np.full(stack.valid_mask.shape, np.nan, dtype="float32")
    risk_map[stack.valid_mask] = risk_normalized
    
    out_risk = resolve(config["paths"]["data_processed"]) / f"risk_index_rf_{config.scenario}.tif"
    write_raster(
        np.where(np.isnan(risk_map), config.nodata, risk_map),
        grid,
        out_risk,
        nodata=config.nodata,
        description=f"RF NDVI anomali tahmini risk indeksi (SPI={args.spi})",
    )
    print(f"\n  Tahmin tamamlandı. Min: {risk_normalized.min():.4f}, Max: {risk_normalized.max():.4f}")

    print("\n[3] Risk sınıflandırması (Jenks vs.)")
    classes, breaks = classify_risk(config, risk_map)
    print(f"  Yöntem: {config['classification']['method']}, {config['classification']['n_classes']} sınıf")
    print("\n" + _indent(class_summary(config, classes, breaks)))

    class_path = resolve(config["paths"]["data_processed"]) / f"risk_class_rf_{config.scenario}.tif"
    write_raster(
        classes, grid, class_path, nodata=0, dtype="uint8",
        description=f"RF kuraklık risk sınıfı 1-5, senaryo: {config.scenario}",
    )

    if config["classification"].get("kmeans_crosscheck"):
        agreement = kmeans_crosscheck(risk_map, config["classification"]["n_classes"])
        print(f"\n  Bağımsız k-means çapraz kontrolü: %{100 * agreement:.1f} sınıf uyumu")

    print("\n[4] Görseller")
    # AD ÇAKIŞMASI TUZAĞI: plot_* varsayılan olarak senaryo adıyla yazar ve bu,
    # AHP figürlerinin (risk_map_<senaryo>.png) üstüne biner. Bu betik bir kez
    # tam da bunu yaptı ve README'nin gösterdiği harita RF çıktısıyla değişti.
    # Çıktı adları bu yüzden açıkça veriliyor.
    from src.visualize import plot_risk_histogram, plot_risk_map

    fig_dir = resolve(config["paths"]["outputs"]) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    for path in (
        plot_risk_map(
            config, grid, classes, breaks,
            out_path=fig_dir / f"risk_map_rf_{config.scenario}.png",
        ),
        plot_risk_histogram(
            config, risk_map, breaks,
            out_path=fig_dir / f"risk_histogram_rf_{config.scenario}.png",
        ),
    ):
        print(f"  {path.relative_to(path.parents[2])}")

    print("\nAdım 16 tamamlandı.")
    return 0

def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())

if __name__ == "__main__":
    raise SystemExit(main())
