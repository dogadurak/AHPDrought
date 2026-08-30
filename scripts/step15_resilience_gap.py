"""Adım 15 — Modül 2 & 3: Resilience Gap (Mekansal Hata Payı) Haritası.

Bu modül, saf fiziksel makine öğrenmesi modelinin "Fiziksel Beklenti"sini kullanarak,
gerçekleşen kuraklık hasarı ile beklenen hasar arasındaki farkı (Residual) hesaplar.

SIGN CONVENTION (İşaret Yönü):
- Hedef Değişken (NDVI Anomalisi): Negatif değerler ortalamanın altında yeşilliği (stresi) temsil eder.
- Beklenen Etki (Predicted Anomaly): Model fiziksel strese göre negatif bir değer öngörür (örn: -0.30).
- Gerçekleşen Etki (Observed Anomaly): Uydudan okunan gerçek değer (örn: -0.10).
- Resilience Gap = Observed - Expected = -0.10 - (-0.30) = +0.20
- SONUÇ: Pozitif Gap değeri, alanın "beklenenden daha az zarar gördüğünü" (daha yüksek direnç / resilience) temsil eder.

DİKKAT: Hesaplamalar sızıntıyı önlemek adına SADECE TARIM ALANLARINDA (Corine = 40) yapılır.
"""

from __future__ import annotations

import argparse
import joblib
import numpy as np
import pandas as pd
from pathlib import Path

from src.config import load_config
from src.grid import build_grid, write_raster
from src.overlay import load_criteria
from src.fetch.common import resolve, interim_path
from src.fetch.climate_series import load_basin_climate_series
from src.grid import read_grid_aligned
from src.drought_index import spi
from src.historical import available_years, landsat_anomaly, severity_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modül 2: Resilience Gap (Residual Analysis)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 15 — MODÜL 2: PURE PHYSICAL RESILIENCE GAP ANALİZİ")
    print("=" * 68)

    model_path = resolve(config["paths"]["data_processed"]) / "rf_drought_model_physical.joblib"
    if not model_path.exists():
        raise FileNotFoundError(f"Model bulunamadı: {model_path}. Önce step14'ü çalıştırın.")

    print("\n[1] Pure Physical Makine Öğrenmesi Modeli Yükleniyor...")
    rf = joblib.load(model_path)
    
    stack = load_criteria(config, grid)
    valid = stack.valid_mask
    
    # Sadece Tarım maskesi
    lc_path = interim_path(config, "landcover.tif")
    lc_codes = read_grid_aligned(lc_path, grid)
    agri_mask = (lc_codes == 40)
    
    valid = valid & agri_mask
    
    feature_names_full = list(stack.names)
    allowed_features = ["precipitation", "soil_awc", "slope", "aspect", "lst"]
    feature_indices = [i for i, name in enumerate(feature_names_full) if name in allowed_features]
    
    features = stack.data[feature_indices, :]
    features = features[:, valid].T

    source = "ndvi"
    years = available_years(config, source=source)
    frame = load_basin_climate_series(config)
    spi12 = spi(frame["ppt"].dropna(), scale=12).values
    severity = severity_index(spi12, years)
    
    # Sadece ağır kurak yılları analiz et
    target_years = [y for y in years if severity[y] <= -1.0]
    
    if not target_years:
        raise SystemExit("Analiz için yeterli şiddetli kuraklık yılı bulunamadı (SPI <= -1.0).")
        
    print(f"\n[2] Şiddetli Kuraklık Yıllarında Resilience Gap Hesaplanıyor...")
    print(f"Analiz edilecek yıllar: {target_years}")
    
    sum_residuals = np.zeros(valid.sum(), dtype="float32")
    count_valid = np.zeros(valid.sum(), dtype="float32")
    
    chunk_size = 500_000
    for year in target_years:
        print(f"  > Yıl {year} (SPI: {severity[year]:.2f}) işleniyor...")
        
        f_spi = np.full((features.shape[0], 1), severity[year])
        features_extended = np.hstack([features, f_spi])
        
        # Beklenen Anomaliyi Tahmin Et (Fiziksel Beklenti)
        # Not: Final modeli kullanıyoruz. Out-of-fold kullanmak teorik olarak daha doğru olsa da
        # yıllar arası spatial tahminler için eğitilmiş final modeli predict etmek pratiktir.
        preds = np.zeros(features_extended.shape[0], dtype="float32")
        for i in range(0, features_extended.shape[0], chunk_size):
            preds[i:i+chunk_size] = rf.predict(features_extended[i:i+chunk_size])
            
        # Gerçekleşen Anomaliyi Oku
        actual_anomaly_map = landsat_anomaly(config, grid, year, years=years, source=source)
        actual_anomaly = actual_anomaly_map[valid]
        
        # Residual (Fark) Hesabı
        # Pozitif = Beklenenden daha yeşil kalmış (Direnç yüksek)
        # Negatif = Beklenenden daha çok hasar görmüş
        valid_pixel_mask = np.isfinite(actual_anomaly)
        
        residuals = np.where(valid_pixel_mask, actual_anomaly - preds, 0)
        sum_residuals += residuals
        count_valid += valid_pixel_mask
        
    # Yılların ortalamasını al
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_residuals = np.where(count_valid > 0, sum_residuals / count_valid, np.nan)
        
    resilience_map = np.full(valid.shape, np.nan, dtype="float32")
    resilience_map[valid] = mean_residuals
    
    # Haritayı diske kaydet
    out_resilience = resolve(config["paths"]["data_processed"]) / "resilience_gap.tif"
    write_raster(
        np.where(np.isnan(resilience_map), config.nodata, resilience_map),
        grid,
        out_resilience,
        nodata=config.nodata,
        description="Resilience Gap (Observed - Expected Anomaly)",
    )
    
    print(f"\n[3] Resilience Gap Haritası Üretildi: {out_resilience.name}")
    valid_resilience = mean_residuals[np.isfinite(mean_residuals)]
    if len(valid_resilience) > 0:
        print(f"  Min Direnç: {valid_resilience.min():+.4f}")
        print(f"  Max Direnç: {valid_resilience.max():+.4f}")
        print(f"  Ort Direnç: {valid_resilience.mean():+.4f}")
        
    print("\nAdım 15 tamamlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
