"""Adım 13 — Risk haritasının gerçek kuraklıklarda sınanması (Landsat dönemi).

Adım 11 "KARAR VERİLEMEZ" ile bitmişti: Sentinel-2 döneminde yalnızca bir kurak
yıl vardı. Landsat 5 (1985-2011, 30 m) havzanın gerçek kuraklıklarını kapsıyor:

    1989-01 – 1991-02   26 ay   SPI-12 en düşük -2.63
    2000-11 – 2001-11   13 ay   SPI-12 en düşük -2.56
    2007-01 – 2007-11   11 ay   SPI-12 en düşük -2.61

Kullanım:
    python -m scripts.step13_historical --fetch     # Landsat serisini üret
    python -m scripts.step13_historical
    python -m scripts.step13_historical --dry-threshold -1.5   # yalnızca şiddetli
"""

from __future__ import annotations

import argparse

import numpy as np

from src.classify import classify_risk
from src.config import load_config
from src.drought_index import spi
from src.fetch.climate_series import load_basin_climate_series
from src.fetch.common import resolve
from src.grid import build_grid
from src.historical import available_years, historical_test, pooled_by_class, summarize
from src.overlay import build_risk_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tarihsel kuraklık sınaması (Adım 13)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--fetch", action="store_true", help="Landsat serisini indir")
    parser.add_argument("--dry-threshold", type=float, default=-1.0,
                        help="Kurak dönem SPI-12 bu değerin altındaki yıllar 'kurak'")
    parser.add_argument("--impact", default="ndvi", choices=("ndvi", "et"),
                        help="Etki ölçüsü: ndvi (Landsat yeşillik) | et (MODIS su kısıtı)")
    parser.add_argument("--landcover-code", type=int, default=40,
                        help="Adil karşılaştırma için sınıf (40 = Cropland, 0 = hepsi)")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 72)
    print("ADIM 13 — GERÇEK KURAKLIKLARDA SINAMA (LANDSAT 5, 1985-2011)")
    print("=" * 72)

    if args.fetch:
        from src.fetch.landsat import fetch_landsat_series

        fetch_landsat_series(config, grid)

    years = available_years(config, args.impact)
    if len(years) < 11:
        raise SystemExit(
            f"Yalnızca {len(years)} Landsat yılı üretilmiş. Önce:\n"
            "  python -m scripts.step13_historical --fetch"
        )
    print(f"\n[1] Landsat yılları: {years[0]}-{years[-1]} ({len(years)} yıl)")

    _, risk, _, _ = build_risk_index(config, grid)
    classes, _ = classify_risk(config, risk)

    frame = load_basin_climate_series(config)
    spi12 = spi(frame["ppt"].dropna(), scale=12).values

    landcover = args.landcover_code or None
    print(f"\n[2] Yıl bazında risk–etki ilişkisi"
          f"{f' (yalnızca arazi örtüsü {landcover})' if landcover else ''}")
    print("    Anomali Landsat döneminin KENDİ İÇİNDE hesaplanıyor; Sentinel")
    print("    dönemiyle karıştırılmıyor (sensör ve arazi kullanımı farkı).")

    result = historical_test(
        config, grid, risk, classes, spi12,
        dry_threshold=args.dry_threshold, landcover_code=landcover, source=args.impact,
    )

    print("\n" + _indent(summarize(config, result)))
    _write_report(config, result, years)
    print(f"\nAdım 13 tamamlandı. Rapor: outputs/reports/historical_test.md")
    return 0


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _write_report(config, result, years) -> None:
    out = resolve(config["paths"]["reports"]) / f"historical_test_{result['source']}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    labels = config["classification"]["labels"]

    parts = [
        "# Risk Haritasının Gerçek Kuraklıklarda Sınanması",
        "",
        f"**Dönem:** Landsat 5, {years[0]}–{years[-1]} ({len(years)} yıl, 30 m)  ",
        f"**Kurak yıl eşiği:** kurak dönem SPI-12 ≤ {result['threshold']}  ",
        f"**Kapsam:** {'yalnızca tarım alanı' if result['landcover_code'] else 'havza geneli'}",
        "",
        "## Neden bu adım gerekliydi",
        "",
        "Adım 11'deki sınama \"KARAR VERİLEMEZ\" ile bitti: Sentinel-2 döneminde",
        "(2017–2025) yalnızca bir kurak yıl vardı ve o da orta şiddetteydi.",
        "68 yıllık yağış kaydında havzanın gerçek kuraklıkları uydu öncesine",
        "düşüyor:",
        "",
        "| Dönem | Süre | En düşük SPI-12 |",
        "|---|---:|---:|",
        "| 1989-01 – 1991-02 | 26 ay | −2,63 |",
        "| 2000-11 – 2001-11 | 13 ay | −2,56 |",
        "| 1991-12 – 1993-01 | 14 ay | −2,29 |",
        "| 2007-01 – 2007-11 | 11 ay | −2,61 |",
        "",
        "Landsat 5 (1984–2011) bu dönemi 30 m'de kapsıyor — projenin grid'iyle",
        "birebir aynı çözünürlük.",
        "",
        "## Sonuçlar",
        "",
        "```",
        summarize(config, result),
        "```",
        "",
        "## Bu sınamanın kendi sınırlılıkları",
        "",
        "1. **Harita bugünkü verilerle kuruldu.** 1990'ı sınarken \"bu mekânsal",
        "   desen 35 yılda değişmedi\" varsayımı yapılıyor. Topoğrafya ve toprak",
        "   için güvenli; **sulama ağı ve arazi örtüsü için tartışmalı** — Gediz'de",
        "   sulu tarım o tarihten bu yana genişledi. Sonuç, haritanın *bugünkü*",
        "   hâlinin *geçmişteki* kuraklıkta ne kadar iyi çalışacağını ölçer.",
        "2. **Sensör farkı.** Landsat 5 TM ile Sentinel-2 MSI aynı NDVI'ı vermez.",
        "   Bu yüzden anomali Landsat döneminin kendi içinde hesaplanır; iki dönem",
        "   hiçbir yerde karıştırılmaz.",
        "3. **NDVI hâlâ dolaylı bir etki ölçüsüdür.** Sulanan parselde yeşillik",
        "   korunurken maliyet artmış olabilir (bkz. Adım 11).",
    ]
    out.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
