"""Adım 3 — Ham katmanlardan 0-1 kriter risk skorları üretir.

Kullanım:
    python -m scripts.step03_build_criteria
    python -m scripts.step03_build_criteria --only slope,aspect --overwrite
    python -m scripts.step03_build_criteria --scenario flat_riskier

Çıktı: data/processed/criteria/<kriter>.tif
"""

from __future__ import annotations

import argparse
import sys

from src.config import load_config
from src.criteria.build import build_criterion
from src.grid import build_grid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kriter raster'larının üretimi (Adım 3)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--only", default=None, help="Virgülle ayrılmış kriter listesi")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    names = config.criteria_order
    if args.only:
        requested = [n.strip() for n in args.only.split(",") if n.strip()]
        unknown = [n for n in requested if n not in names]
        if unknown:
            raise SystemExit(f"Bilinmeyen kriter: {unknown}. Seçenekler: {names}")
        names = requested

    print("=" * 68)
    print("ADIM 3 — KRİTER RASTER'LARI")
    print(f"Senaryo: {config.scenario}")
    print(f"Kriterler: {', '.join(names)}")
    print("=" * 68)

    failures = []
    for name in names:
        try:
            build_criterion(name, config, grid, overwrite=args.overwrite)
        except Exception as exc:
            failures.append((name, exc))
            print(f"      BAŞARISIZ: {type(exc).__name__}: {exc}", file=sys.stderr)

    print("\n" + "=" * 68)
    if failures:
        print(f"{len(failures)} kriter başarısız:")
        for name, exc in failures:
            print(f"  - {name}: {type(exc).__name__}: {exc}")
        return 1

    print(f"Adım 3 tamamlandı — {len(names)} kriter data/processed/criteria/ altında.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
