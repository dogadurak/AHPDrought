"""Adım 4-5 — Makine Öğrenmesi (RF) tabanlı risk haritası üretimi ve sınıflandırması.

Bu betik, AHP yerine Adım 14'te eğitilmiş olan Random Forest modelini kullanarak
risk haritası (NDVI anomalisi tahmini) üretir. Risk, beklenen hasarın (anomalinin)
tersi olarak düşünülüp 0-1 arasına ölçeklenir ve 5 sınıfa ayrılır.

Kullanım:
    python -m scripts.step04_risk_map
    python -m scripts.step04_risk_map --scenario severe_drought --spi -2.0
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
    parser = argparse.ArgumentParser(description="ML Risk haritası üretimi (Adım 4-5)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--spi", type=float, default=-2.0, help="Drought severity scenario (SPI-12)")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 4-5 — ML (RANDOM FOREST) ÇAKIŞTIRMA VE RİSK SINIFLANDIRMASI")
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
    
    out_risk = resolve(config["paths"]["data_processed"]) / f"risk_index_{config.scenario}.tif"
    write_raster(
        np.where(np.isnan(risk_map), config.nodata, risk_map),
        grid,
        out_risk,
        nodata=config.nodata,
        description=f"ML NDVI Anomaly Risk Index (SPI={args.spi})",
    )
    print(f"\n  Tahmin tamamlandı. Min: {risk_normalized.min():.4f}, Max: {risk_normalized.max():.4f}")

    print("\n[3] Risk sınıflandırması (Jenks vs.)")
    classes, breaks = classify_risk(config, risk_map)
    print(f"  Yöntem: {config['classification']['method']}, {config['classification']['n_classes']} sınıf")
    print("\n" + _indent(class_summary(config, classes, breaks)))

    class_path = resolve(config["paths"]["data_processed"]) / f"risk_class_{config.scenario}.tif"
    write_raster(
        classes, grid, class_path, nodata=0, dtype="uint8",
        description=f"Kuraklık risk sınıfı 1-5, senaryo: {config.scenario}",
    )

    if config["classification"].get("kmeans_crosscheck"):
        agreement = kmeans_crosscheck(risk_map, config["classification"]["n_classes"])
        print(f"\n  Bağımsız k-means çapraz kontrolü: %{100 * agreement:.1f} sınıf uyumu")

    print("\n[4] Görseller")
    from src.visualize import plot_risk_histogram, plot_risk_map
    for path in (
        plot_risk_map(config, grid, classes, breaks),
        plot_risk_histogram(config, risk_map, breaks),
    ):
        print(f"  {path.relative_to(path.parents[2])}")

    print(f"\nAdım 4-5 tamamlandı.")
    return 0

def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())

if __name__ == "__main__":
    raise SystemExit(main())
