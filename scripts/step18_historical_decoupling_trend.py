"""Adım 18 — Modül 4: Historical Decoupling Trend (Zamana Bağlı Ayrışma).

Bu modül, zaman içinde tarım alanlarındaki sulama altyapısının artmasıyla
birlikte, fiziksel kuraklık riskinin (eğim, toprak) gerçekleşen hasarı
açıklama gücünün nasıl azaldığını (Decoupling) test eder.
"""

from __future__ import annotations

import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import spearmanr, linregress

from src.config import load_config
from src.grid import build_grid, read_grid_aligned
from src.fetch.common import interim_path, resolve
from src.fetch.climate_series import load_basin_climate_series
from src.drought_index import spi
from src.historical import available_years, landsat_anomaly, severity_index

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modül 4: Historical Decoupling Trend")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 18 — MODÜL 4: HISTORICAL DECOUPLING TREND (ZAMANSAL AYRIŞMA)")
    print("=" * 68)

    # 1. Yukleme
    out_dir = resolve(config["paths"]["data_processed"])
    risk_index_path = out_dir / f"risk_index_{config.scenario}.tif"
    
    if not risk_index_path.exists():
        raise FileNotFoundError(f"Risk haritası bulunamadı: {risk_index_path}")
        
    risk_index = read_grid_aligned(risk_index_path, grid)
    landcover = read_grid_aligned(interim_path(config, "landcover.tif"), grid)
    
    frame = load_basin_climate_series(config)
    spi12 = spi(frame["ppt"].dropna(), scale=12).values
    
    source = "ndvi"
    years = available_years(config, source=source)
    severity = severity_index(spi12, years)
    
    # 2. Sadece Tarım Alanlarını (40) Filtrele
    crop_mask = (landcover == 40) & np.isfinite(risk_index)
    risk_crop = risk_index[crop_mask]
    
    if crop_mask.sum() == 0:
        raise ValueError("Tarım alanı maskesinde geçerli veri bulunamadı.")
        
    print("\n[1] Yıllara Göre Tarım Alanlarında Risk-Etki Korelasyonu Hesaplanıyor...")
    
    results = []
    
    for year in sorted(years):
        anomaly_map = landsat_anomaly(config, grid, year, years=years, source=source)
        anomaly_crop = anomaly_map[crop_mask]
        
        valid = np.isfinite(anomaly_crop)
        if valid.sum() > 100:
            rho, _ = spearmanr(risk_crop[valid], anomaly_crop[valid])
            is_dry = severity[year] <= -1.0
            results.append({
                "year": year,
                "rho": rho,
                "spi": severity[year],
                "is_dry": is_dry
            })
            print(f"  > {year}: SPI={severity[year]:+.2f} | r={rho:+.4f} {'(KURAK)' if is_dry else ''}")

    if not results:
        print("Hesaplanabilen yıl bulunamadı.")
        return 1
        
    # 3. Görselleştirme
    fig, ax = plt.subplots(figsize=(10, 6))
    
    dry_years = [r for r in results if r["is_dry"]]
    normal_years = [r for r in results if not r["is_dry"]]
    
    if dry_years:
        ax.scatter([r["year"] for r in dry_years], [r["rho"] for r in dry_years], 
                   color='red', s=80, label='Kurak Yıllar (SPI <= -1.0)', zorder=5)
                   
    if normal_years:
        ax.scatter([r["year"] for r in normal_years], [r["rho"] for r in normal_years], 
                   color='blue', s=40, alpha=0.5, label='Normal Yıllar', zorder=4)
                   
    # Kurak yıllar için trend line (Eğer en az 3 yıl varsa)
    if len(dry_years) >= 3:
        x = np.array([r["year"] for r in dry_years])
        y = np.array([r["rho"] for r in dry_years])
        slope, intercept, r_value, p_value, std_err = linregress(x, y)
        
        x_trend = np.linspace(min(x)-1, max(x)+1, 100)
        y_trend = slope * x_trend + intercept
        
        ax.plot(x_trend, y_trend, 'r--', linewidth=2, 
                label=f'Trend (Kurak Yıllar): Eğimi={slope:+.4f} (p={p_value:.2f})')
        
        if slope > 0:
            msg = "Zamanla korelasyon sıfıra (0) doğru zayıflıyor.\nBu, sulama altyapısının genişlemesiyle fiziksel modelin başarısızlaştığını gösterir."
            ax.text(0.5, 0.95, msg, transform=ax.transAxes, ha='center', va='top', 
                    bbox=dict(boxstyle='round', facecolor='white', alpha=0.8), fontsize=10)
    
    ax.axhline(0, color='black', linewidth=1)
    ax.set_xlabel("Yıl", fontsize=11)
    ax.set_ylabel("Risk-Hasar Korelasyonu (r)", fontsize=11)
    ax.set_title("Tarım Alanlarında Kuraklık Riskinin Açıklayıcılığının Zaman İçindeki Değişimi", fontsize=13)
    ax.legend(loc='lower right')
    ax.grid(True, linestyle='--', alpha=0.7)
    
    plt.tight_layout()
    
    fig_dir = resolve(config["paths"]["outputs"]) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    out_fig = fig_dir / "historical_decoupling_trend.png"
    plt.savefig(out_fig, dpi=150)
    
    print(f"\n[2] Grafik kaydedildi: {out_fig}")
    print("\nAdım 18 tamamlandı.")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
