"""Adım 2 — Tüm kriter girdilerini indirir ve ortak grid'e hizalar.

Kullanım:
    python -m scripts.step02_fetch_data                    # hepsi
    python -m scripts.step02_fetch_data --only dem,water   # seçili katmanlar
    python -m scripts.step02_fetch_data --list             # katmanları ve süreleri göster
    python -m scripts.step02_fetch_data --years 2023 2024  # referans yılları daralt
    python -m scripts.step02_fetch_data --only ndvi-dry --overwrite

Her katman kendi çıktısını `data/interim/` altına yazar ve dosya varsa
atlanır; iş kesilirse aynı komut kaldığı yerden devam eder.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable

from src.config import Config, load_config
from src.fetch import (
    fetch_chirps,
    fetch_dem,
    fetch_et_ratio,
    fetch_irrigation_features,
    fetch_lst,
    fetch_ndvi_dry_composite,
    fetch_ndvi_timeseries,
    fetch_soil_awc,
    fetch_water_features,
    fetch_worldcover,
)
from src.grid import TargetGrid, build_grid

# (isim, fonksiyon, kabaca beklenen süre) — süreler tam grid ve 6 referans yılı içindir.
LAYERS: dict[str, tuple[Callable, str]] = {
    "dem": (fetch_dem, "~10 sn"),
    "landcover": (fetch_worldcover, "~15 sn"),
    "lst": (fetch_lst, "~2 dk"),
    "precipitation": (fetch_chirps, "~5 dk (ilk sefer ~270 MB indirme)"),
    "water": (fetch_water_features, "~1 dk"),
    "irrigation": (fetch_irrigation_features, "~1 dk"),
    "soil": (fetch_soil_awc, "~2 dk (SoilGrids WCS, 6 katman)"),
    "ndvi-dry": (fetch_ndvi_dry_composite, "~60 dk (18 aylık kompozit)"),
    "ndvi-series": (fetch_ndvi_timeseries, "~30 dk (12 ay; 3'ü kurak dönemle ortak)"),
    # Kriter değil — Adım 7'nin bağımsız doğrulama girdisi.
    "et-ratio": (fetch_et_ratio, "~1 dk (doğrulama için, kriter değil)"),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Veri indirme (Adım 2)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument(
        "--only",
        default=None,
        help=f"Virgülle ayrılmış katman listesi. Seçenekler: {', '.join(LAYERS)}",
    )
    parser.add_argument("--overwrite", action="store_true", help="Önbelleği yok say")
    parser.add_argument("--years", nargs="+", type=int, default=None, help="Referans yıllarını değiştir")
    parser.add_argument("--list", action="store_true", help="Katmanları listele ve çık")
    args = parser.parse_args(argv)

    if args.list:
        print(f"{'Katman':<16}{'Beklenen süre'}")
        print("-" * 56)
        for name, (_, duration) in LAYERS.items():
            print(f"{name:<16}{duration}")
        return 0

    selected = _select(args.only)
    config = load_config(args.config, scenario=args.scenario)

    if args.years:
        config.raw["periods"]["reference_years"] = args.years
        print(f"Referans yılları geçersiz kılındı: {args.years}")

    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 2 — VERİ İNDİRME")
    print(f"Grid: {grid.width}x{grid.height} @ {grid.resolution:g} m, {grid.crs}")
    print(f"Referans yılları: {config['periods']['reference_years']}")
    print(f"Katmanlar: {', '.join(selected)}")
    print("=" * 68)

    failures: list[tuple[str, Exception]] = []
    started = time.time()

    for name in selected:
        func, duration = LAYERS[name]
        print(f"\n--- {name} ({duration}) ---")
        layer_start = time.time()
        try:
            func(config, grid, overwrite=args.overwrite)
            print(f"  tamamlandı ({time.time() - layer_start:.1f} sn)")
        except Exception as exc:  # bir katmanın hatası diğerlerini durdurmasın
            failures.append((name, exc))
            print(f"  BAŞARISIZ: {type(exc).__name__}: {exc}", file=sys.stderr)

    print("\n" + "=" * 68)
    print(f"Toplam süre: {(time.time() - started) / 60:.1f} dk")
    if failures:
        print(f"{len(failures)} katman başarısız:")
        for name, exc in failures:
            print(f"  - {name}: {type(exc).__name__}: {exc}")
        return 1

    print("Adım 2 tamamlandı — tüm katmanlar data/interim/ altında.")
    return 0


def _select(only: str | None) -> list[str]:
    if not only:
        return list(LAYERS)
    names = [n.strip() for n in only.split(",") if n.strip()]
    unknown = [n for n in names if n not in LAYERS]
    if unknown:
        raise SystemExit(f"Bilinmeyen katman: {unknown}. Seçenekler: {list(LAYERS)}")
    return names


if __name__ == "__main__":
    raise SystemExit(main())
