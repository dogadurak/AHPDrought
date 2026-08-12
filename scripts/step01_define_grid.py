"""Adım 1 — AOI ve ortak grid'i üretir, AHP matrisinin tutarlılığını doğrular.

Kullanım:
    python -m scripts.step01_define_grid
    python -m scripts.step01_define_grid --scenario flat_riskier

Çıktılar:
    data/processed/aoi.geojson
    data/processed/grid_definition.json
"""

from __future__ import annotations

import argparse
import sys

from src.ahp import InconsistentMatrixError, geometric_mean_weights, solve_from_config
from src.aoi import build_aoi, save_aoi
from src.config import load_config
from src.grid import build_grid, save_grid_definition


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AOI + ortak grid tanımı (Adım 1)")
    parser.add_argument("--config", default=None, help="Alternatif config.yaml yolu")
    parser.add_argument("--scenario", default=None, help="scenarios.definitions altındaki bir isim")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)

    print("=" * 68)
    print(config["project"]["name"])
    print(f"Senaryo: {config.scenario}")
    print("=" * 68)

    # --- AOI ---------------------------------------------------------------
    aoi = build_aoi(config)
    aoi_path = save_aoi(aoi, config["paths"]["aoi_file"])

    aoi_utm = aoi.to_crs(config.crs)
    aoi_area_km2 = float(aoi_utm.area.iloc[0]) / 1e6

    print("\n[AOI]")
    print(f"  Ad          : {config['aoi']['name']}")
    print(f"  Kaynak      : {aoi['source'].iloc[0]}")
    print(f"  bbox (WGS84): {config['aoi']['bbox_wgs84']}")
    print(f"  Alan        : {aoi_area_km2:,.1f} km²")
    print(f"  Yazıldı     : {aoi_path.relative_to(aoi_path.parents[2])}")

    # --- Grid --------------------------------------------------------------
    grid = build_grid(config)
    grid_path = save_grid_definition(grid, config["paths"]["grid_file"])

    left, bottom, right, top = grid.bounds
    print("\n[ORTAK GRID]")
    print(f"  CRS         : {grid.crs}  (UTM 35N)")
    print(f"  Çözünürlük  : {grid.resolution:g} m")
    print(f"  Boyut       : {grid.width} sütun x {grid.height} satır = {grid.cell_count:,} hücre")
    print(f"  Kapsam      : {right - left:,.0f} m x {top - bottom:,.0f} m  ({grid.area_km2:,.1f} km²)")
    print(f"  Sol-üst köşe: ({left:,.0f}, {top:,.0f})")
    print(f"  Katman başı : ~{grid.cell_count * 4 / 1e6:,.1f} MB (float32)")
    print(f"  Yazıldı     : {grid_path.relative_to(grid_path.parents[2])}")

    # --- AHP tutarlılık kontrolü -------------------------------------------
    print("\n[AHP — İKİLİ KARŞILAŞTIRMA MATRİSİ]")
    try:
        result = solve_from_config(config)
    except InconsistentMatrixError as exc:
        print(f"  HATA: {exc}", file=sys.stderr)
        return 1

    print("  " + result.summary().replace("\n", "\n  "))

    gm = geometric_mean_weights(config["ahp"]["matrix"])
    max_dev = float(abs(gm - result.weights).max())
    print(f"\n  Çapraz kontrol (geometrik ortalama yöntemi): max sapma = {max_dev:.5f}")

    max_cr = config["ahp"]["consistency"]["max_cr"]
    verdict = "KABUL" if result.consistency_ratio <= max_cr else "RED"
    print(f"  Karar: CR = {result.consistency_ratio:.4f} <= {max_cr} -> {verdict}")

    print("\nAdım 1 tamamlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
