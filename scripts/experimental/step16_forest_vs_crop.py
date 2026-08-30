"""Adım 16 — Modül 1: Doğal Alan (Orman) vs Tarım Alanı Sınaması.

Bu modül, AHP veya Fiziksel ML modeli ile üretilen kuraklık risk haritasının
doğal alanlarda (orman - 20) ve insan müdahaleli alanlarda (tarım - 40)
farklı Risk-Etki ayrışması (Decoupling) yaşayıp yaşamadığını test eder.
"""

from __future__ import annotations

import argparse
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

from src.config import load_config
from src.grid import build_grid, read_grid_aligned
from src.fetch.common import interim_path, resolve
from src.fetch.climate_series import load_basin_climate_series
from src.drought_index import spi
from src.historical import historical_test, available_years


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modül 1: Forest vs Crop (Managed vs Natural Ecosystems)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 16 — MODÜL 1: MANAGED VS NATURAL ECOSYSTEMS (FOREST VS CROP)")
    print("=" * 68)

    # 1. Yukleme
    out_dir = resolve(config["paths"]["data_processed"])
    risk_index_path = out_dir / f"risk_index_{config.scenario}.tif"
    risk_class_path = out_dir / f"risk_class_{config.scenario}.tif"
    
    if not risk_index_path.exists():
        raise FileNotFoundError(f"Risk haritası bulunamadı: {risk_index_path}")
        
    risk_index = read_grid_aligned(risk_index_path, grid)
    risk_classes = read_grid_aligned(risk_class_path, grid)
    
    frame = load_basin_climate_series(config)
    spi12 = spi(frame["ppt"].dropna(), scale=12).values
    
    print("\n[1] Orman (Doğal Alan - 20) için Korelasyon Hesaplanıyor...")
    res_forest = historical_test(
        config, grid, risk_index, risk_classes, spi12, 
        landcover_code=20, source="ndvi"
    )
    
    print("\n[2] Tarım (Müdahaleli Alan - 40) için Korelasyon Hesaplanıyor...")
    res_crop = historical_test(
        config, grid, risk_index, risk_classes, spi12, 
        landcover_code=40, source="ndvi"
    )
    
    # 3. Karsilastirma ve Gorsellestirme
    forest_dry_rho = res_forest.get("dry_rho", np.nan)
    crop_dry_rho = res_crop.get("dry_rho", np.nan)
    
    print("\n[SONUÇ: RISK-IMPACT DECOUPLING]")
    print(f"Orman (Doğal) Korelasyon (r): {forest_dry_rho:+.4f}")
    print(f"Tarım (Yönetilen) Korelasyon (r): {crop_dry_rho:+.4f}")
    
    if np.isnan(forest_dry_rho) or np.isnan(crop_dry_rho):
        print("Uyarı: Yeterli kurak yıl bulunamadı. Grafik çizilemiyor.")
        return 1

    fig, ax = plt.subplots(figsize=(8, 6))
    
    labels = ['Orman (Doğal Ekosistem)', 'Tarım (İnsan Yönetimli)']
    values = [forest_dry_rho, crop_dry_rho]
    
    # Negatif korelasyon = yüksek riskin negatif anomaliyle (hasarla) eşleşmesi (beklenen durum)
    # Pozitif veya sıfır = decoupling (uyumsuzluk)
    colors = ['#2ca02c', '#d62728'] # Orman yeşil, Tarım kırmızı
    
    bars = ax.bar(labels, values, color=colors, width=0.5)
    ax.axhline(0, color='black', linewidth=1)
    
    ax.set_ylabel("Fiziksel Risk ile Gerçekleşen Hasar (NDVI) Korelasyonu (r)", fontsize=11)
    ax.set_title("Fiziksel Beklenti vs Gerçekleşen Etki (Risk-Impact Decoupling)", fontsize=13)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, yval + (0.01 if yval>0 else -0.02), 
                f"{yval:+.3f}", ha='center', va='bottom' if yval>0 else 'top', fontweight='bold')
                
    ax.text(0.5, 0.95, "Sıfıra yakın (0.0) değerler, fiziksel riskin hasarı hiç açıklayamadığını gösterir\n(İnsan Faktörü / Sulama Etkisi)", 
            transform=ax.transAxes, ha='center', va='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8), fontsize=10)
    
    fig_dir = resolve(config["paths"]["outputs"]) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    out_fig = fig_dir / "forest_vs_crop_correlation.png"
    
    plt.tight_layout()
    plt.savefig(out_fig, dpi=150)
    print(f"\nGrafik kaydedildi: {out_fig}")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
