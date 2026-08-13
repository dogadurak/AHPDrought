"""Adım 7 — Doğrulama raporu.

Kullanım:
    python -m scripts.step07_validate

Çıktı: outputs/reports/validation_report.md
"""

from __future__ import annotations

import argparse

from src.classify import classify_risk
from src.config import load_config
from src.grid import build_grid
from src.overlay import build_risk_index
from src.validate import (
    amplitude_by_class,
    et_ratio,
    et_ratio_by_class,
    rank_correlation,
    risk_by_elevation,
    risk_by_landcover,
    scenario_agreement,
    seasonal_amplitude,
    write_validation_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Doğrulama raporu (Adım 7)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 7 — DOĞRULAMA")
    print("=" * 68)

    _, risk, _, _ = build_risk_index(config, grid)
    classes, _ = classify_risk(config, risk)

    print("\n[1] Senaryo dayanıklılığı")
    agreement = scenario_agreement(config, grid)
    print(f"  {agreement['scenarios'][0]} vs {agreement['scenarios'][1]}")
    print(f"  Risk indeksi ortalama farkı : {agreement['mean_abs_diff']:.4f}")
    print(f"  Aynı sınıfta kalan piksel   : %{100 * agreement['class_agreement']:.1f}")
    print(f"  En fazla 1 sınıf kayan      : %{100 * agreement['within_one_class']:.1f}")

    print("\n[2] Buharlaşma oranı ET/PET (BAĞIMSIZ — modele hiç girmedi)")
    ratio = et_ratio(config, grid)
    labels = config["classification"]["labels"]
    if ratio is None:
        print("  et_pet_ratio.tif yok — `--only et-ratio` ile üretin")
    else:
        rows = et_ratio_by_class(classes, ratio, config["classification"]["n_classes"])
        for code, mean_ratio, count in rows:
            print(f"  {code} — {labels[code]:<12} ET/PET {mean_ratio:.4f}  ({count:,} piksel)")
        monotone = all(rows[i][1] >= rows[i + 1][1] for i in range(len(rows) - 1))
        print(f"  Risk indeksi ile Spearman ρ = {rank_correlation(risk, ratio):.4f}")
        print(f"  Beklenti (risk arttıkça ET/PET azalmalı): {'DOĞRULANDI' if monotone else 'DOĞRULANMADI'}")

    print("\n[3] Mevsimsel NDVI genliği (yarı bağımsız)")
    amplitude = seasonal_amplitude(config, grid)
    if amplitude is None:
        print("  Aylık kompozitler eksik — atlandı")
    else:
        rows = amplitude_by_class(classes, amplitude, config["classification"]["n_classes"])
        for code, mean_amp, count in rows:
            print(f"  {code} — {labels[code]:<12} ortalama mevsimsel düşüş {mean_amp:.4f}  ({count:,} piksel)")
        monotone = all(rows[i][1] <= rows[i + 1][1] for i in range(len(rows) - 1))
        print(f"  Beklenti (risk arttıkça genlik artmalı): {'DOĞRULANDI' if monotone else 'DOĞRULANMADI'}")

    print("\n[4] Arazi örtüsüne göre ortalama risk")
    for name, mean_risk, share in risk_by_landcover(config, grid, risk):
        print(f"  {name:<30} {mean_risk:.4f}   (alanın %{share:.1f}'i)")

    print("\n[5] Yükseklik kuşağına göre ortalama risk")
    for band, mean_risk, count in risk_by_elevation(config, grid, risk):
        print(f"  {band:<18} {mean_risk:.4f}   ({count:,} piksel)")

    out = write_validation_report(config, grid, risk, classes)
    print(f"\nAdım 7 tamamlandı. Rapor: {out.relative_to(out.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
