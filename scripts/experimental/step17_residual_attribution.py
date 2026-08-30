"""Adım 17 — Modül 3: Residual Attribution (Direnç Kaynaklarının Analizi).

Bu modül, hesaplanan 'Resilience Gap' (Beklenen - Gerçekleşen Hasar)
haritasındaki direncin mekansal dağılımını, fiziksel (eğim, toprak) ve 
insan/yönetim (sulama kanallarına uzaklık) faktörleriyle korelasyon kurarak açıklar.

Ayrıca OLS Multiple Regression ile confounder kontrolü yapar.
"""

from __future__ import annotations

import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import spearmanr
import statsmodels.api as sm

from src.config import load_config
from src.grid import build_grid, read_grid_aligned
from src.fetch.common import interim_path, resolve

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Modül 3: Residual Attribution")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 17 — MODÜL 3: RESIDUAL ATTRIBUTION & CONFOUNDER CONTROL")
    print("=" * 68)

    # 1. Resilience Gap ve Landcover Yükle
    out_dir = resolve(config["paths"]["data_processed"])
    resilience_path = out_dir / "resilience_gap.tif"
    
    if not resilience_path.exists():
        raise FileNotFoundError(f"Resilience Gap haritası bulunamadı: {resilience_path}")
        
    resilience = read_grid_aligned(resilience_path, grid)
    resilience[resilience == config.nodata] = np.nan
    
    landcover = read_grid_aligned(interim_path(config, "landcover.tif"), grid)
    
    # 2. Sadece Tarım Alanlarını (40) Filtrele
    crop_mask = (landcover == 40) & np.isfinite(resilience)
    
    if crop_mask.sum() == 0:
        raise ValueError("Tarım alanı maskesinde geçerli veri bulunamadı.")
        
    res_crop = resilience[crop_mask]
    
    # 3. Bağımsız Değişkenleri Yükle
    factors = {
        "dist_irrig": "distance_to_irrigation.tif",
        "elevation": "dem.tif",
        "slope": "slope.tif",
        "soil_awc": "soil_awc.tif",
        "lst": "lst.tif",
        "precip": "precipitation.tif"
    }
    
    data_dict = {"resilience_gap": res_crop}
    
    for name, filename in factors.items():
        filepath = interim_path(config, filename)
        if filepath.exists():
            arr = read_grid_aligned(filepath, grid)
            arr[arr == config.nodata] = np.nan
            data_dict[name] = arr[crop_mask]
        else:
            print(f"Uyarı: {filename} bulunamadı.")
            
    df = pd.DataFrame(data_dict).dropna()
    print(f"\nGeçerli piksel sayısı: {len(df)}")
    
    if len(df) == 0:
        return 1

    # 4. Spearman Korelasyonu
    print("\n[1] Bivariate Spearman Korelasyonları:")
    correlations = {}
    for col in df.columns:
        if col == "resilience_gap": continue
        rho, pval = spearmanr(df["resilience_gap"], df[col])
        correlations[col] = rho
        print(f"  > {col:15}: r = {rho:+.4f} (p={pval:.2e})")

    # 5. Q1-Q4 Quantile Analizi (Distance to Irrigation)
    if "dist_irrig" in df.columns:
        print("\n[2] Sulamaya Uzaklık (Quantile) Analizi:")
        df['dist_quantile'] = pd.qcut(df['dist_irrig'], q=4, labels=['Q1 (Yakın)', 'Q2', 'Q3', 'Q4 (Uzak)'])
        
        agg_df = df.groupby('dist_quantile', observed=False).agg(
            mean_gap=('resilience_gap', 'mean'),
            median_gap=('resilience_gap', 'median'),
            std_gap=('resilience_gap', 'std'),
            count=('resilience_gap', 'count')
        )
        # Basit Confidence Interval (95%)
        agg_df['ci_95'] = 1.96 * (agg_df['std_gap'] / np.sqrt(agg_df['count']))
        print(agg_df)
        
    # 6. Confounder Kontrolü (Multiple OLS Regression)
    print("\n[3] Confounder Kontrolü (Multivariate OLS):")
    # Değişkenleri standardize et ki katsayılar (effect size) karşılaştırılabilsin
    df_std = (df.select_dtypes(include=[np.number]) - df.select_dtypes(include=[np.number]).mean()) / df.select_dtypes(include=[np.number]).std()
    
    X_cols = [c for c in df_std.columns if c != 'resilience_gap']
    X = df_std[X_cols]
    X = sm.add_constant(X)
    y = df_std['resilience_gap']
    
    model = sm.OLS(y, X).fit()
    print(model.summary().tables[1])
    
    print("\nNOT: Model katsayıları standardize edilmiştir (Beta coeff).")
    print("Eğer dist_irrig'in katsayısı hala anlamlı (ve negatif) ise, sulamanın etkisi")
    print("yalnızca topografya veya yağışın bir yansıması (confounder) değildir.")

    # 7. Görselleştirme (Korelasyonlar)
    fig, ax = plt.subplots(figsize=(10, 6))
    names = list(correlations.keys())
    rhos = list(correlations.values())
    colors = ['#1f77b4' if n == 'dist_irrig' else '#7f7f7f' for n in names]
    
    y_pos = np.arange(len(names))
    bars = ax.barh(y_pos, rhos, align='center', color=colors)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    
    ax.set_xlabel("Spearman Korelasyonu (r)", fontsize=11)
    ax.set_title("Tarım Alanlarında Direnci Açıklayan Faktörler", fontsize=13)
    ax.axvline(0, color='black', linewidth=1)
    ax.grid(axis='x', linestyle='--', alpha=0.7)
    
    fig_dir = resolve(config["paths"]["outputs"]) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    out_fig = fig_dir / "resilience_attribution.png"
    plt.tight_layout()
    plt.savefig(out_fig, dpi=150)
    
    print(f"\n[4] Grafik kaydedildi: {out_fig}")
    print("\nAdım 17 tamamlandı.")
    
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
