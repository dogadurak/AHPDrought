"""Adım 6 — NDVI zaman serisi animasyonu ve parsel eğrileri.

Kullanım:
    python -m scripts.step06_ndvi_timeseries
    python -m scripts.step06_ndvi_timeseries --downsample 4 --fps 2
"""

from __future__ import annotations

import argparse

from src.animate import make_ndvi_animation, monthly_paths, plot_parcel_curves
from src.config import load_config
from src.grid import build_grid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NDVI zaman serisi görselleri (Adım 6)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--downsample", type=int, default=3, help="GIF için piksel seyreltme")
    parser.add_argument("--fps", type=float, default=1.6)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 6 — NDVI ZAMAN SERİSİ")
    print("=" * 68)

    available = monthly_paths(config)
    year = config["periods"]["timeseries"]["year"]
    print(f"\n[1] {year} yılı için {len(available)}/12 aylık kompozit bulundu")
    if len(available) < 12:
        missing = set(range(1, 13)) - {m for m, _ in available}
        print(f"    Eksik aylar: {sorted(missing)} — animasyon eksik karelerle üretilecek")

    print("\n[2] Animasyon")
    gif = make_ndvi_animation(config, grid, downsample=args.downsample, fps=args.fps)
    print(f"  {gif.relative_to(gif.parents[2])}")

    print("\n[3] Örnek parsel eğrileri")
    curves = plot_parcel_curves(config, grid)
    print(f"  {curves.relative_to(curves.parents[2])}")
    print(f"  {curves.with_suffix('.md').relative_to(curves.parents[2])}  (sayısal tablo)")

    print("\nAdım 6 tamamlandı.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
