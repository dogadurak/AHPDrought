"""Adım 4-5 — AHP ağırlıklı çakıştırma, duyarlılık analizi ve risk sınıflandırması.

Kullanım:
    python -m scripts.step04_risk_map
    python -m scripts.step04_risk_map --scenario flat_riskier
    python -m scripts.step04_risk_map --skip-sensitivity   # hızlı deneme

Çıktılar:
    data/processed/risk_index_<senaryo>.tif    sürekli indeks (0-1)
    data/processed/risk_class_<senaryo>.tif    5 sınıflı risk (1-5)
    outputs/reports/ahp_<senaryo>.md           ağırlıklar + duyarlılık tablosu
"""

from __future__ import annotations

import argparse

import numpy as np

from src.classify import class_summary, classify_risk, kmeans_crosscheck
from src.config import load_config
from src.fetch.common import resolve
from src.grid import build_grid, write_raster
from src.overlay import (
    build_risk_index,
    contribution_report,
    sensitivity_analysis,
    sensitivity_table,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Risk haritası üretimi (Adım 4-5)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--skip-sensitivity", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 68)
    print("ADIM 4-5 — AHP ÇAKIŞTIRMA VE RİSK SINIFLANDIRMASI")
    print(f"Senaryo: {config.scenario}")
    print("=" * 68)

    # --- AHP ağırlıkları ---------------------------------------------------
    print("\n[1] AHP ağırlıkları")
    _, risk, result, stack = build_risk_index(config, grid, overwrite=args.overwrite)
    print("\n" + _indent(result.summary()))

    print("\n[2] Nominal ağırlık vs efektif katkı")
    print(_indent(contribution_report(stack, result)))

    # --- Sınıflandırma -----------------------------------------------------
    print("\n[3] Risk sınıflandırması")
    classes, breaks = classify_risk(config, risk)
    print(f"  Yöntem: {config['classification']['method']}, {config['classification']['n_classes']} sınıf")
    print("\n" + _indent(class_summary(config, classes, breaks)))

    class_path = resolve(config["paths"]["data_processed"]) / f"risk_class_{config.scenario}.tif"
    write_raster(
        classes, grid, class_path, nodata=0, dtype="uint8",
        description=f"Kuraklık risk sınıfı 1-5, senaryo: {config.scenario}",
    )

    agreement = None
    if config["classification"].get("kmeans_crosscheck"):
        agreement = kmeans_crosscheck(risk, config["classification"]["n_classes"])
        print(f"\n  Bağımsız k-means çapraz kontrolü: %{100 * agreement:.1f} sınıf uyumu")

    # --- Duyarlılık --------------------------------------------------------
    rows = []
    if not args.skip_sensitivity:
        print("\n[4] Duyarlılık analizi (her ağırlık ±%{:.0f})".format(
            100 * config["sensitivity"]["weight_perturbation"]))
        rows = sensitivity_analysis(
            config, stack, result, risk,
            n_classes=config["classification"]["n_classes"],
            breaks=breaks,
        )
        print("\n" + _indent(sensitivity_table(rows)))

    # --- Görseller ---------------------------------------------------------
    print("\n[5] Görseller")
    from src.visualize import plot_criteria_panel, plot_risk_histogram, plot_risk_map

    for path in (
        plot_risk_map(config, grid, classes, breaks),
        plot_criteria_panel(config, grid, stack, result),
        plot_risk_histogram(config, risk, breaks),
    ):
        print(f"  {path.relative_to(path.parents[2])}")

    _write_report(config, result, stack, classes, breaks, rows, agreement)
    print(f"\nAdım 4-5 tamamlandı. Rapor: outputs/reports/ahp_{config.scenario}.md")
    return 0


def _indent(text: str, prefix: str = "  ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _write_report(config, result, stack, classes, breaks, rows, agreement=None) -> None:
    out = resolve(config["paths"]["reports"]) / f"ahp_{config.scenario}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    parts = [
        f"# AHP Kuraklık Risk Analizi — senaryo `{config.scenario}`",
        "",
        f"**Bölge:** {config['aoi']['name']}  ",
        f"**Grid:** {config.crs}, {config.resolution:g} m  ",
        f"**Referans yılları:** {config['periods']['reference_years']}",
        "",
        "## 1. AHP ağırlıkları",
        "",
        "```",
        result.summary(),
        "```",
        "",
        f"Tutarlılık oranı CR = {result.consistency_ratio:.4f} "
        f"(eşik {config['ahp']['consistency']['max_cr']}) — matris kabul edildi.",
        "",
        "## 2. Nominal ağırlık ve efektif katkı",
        "",
        "```",
        contribution_report(stack, result),
        "```",
        "",
        "## 3. Risk sınıfları",
        "",
        "```",
        class_summary(config, classes, breaks),
        "```",
    ]

    if rows:
        parts += [
            "",
            f"## 4. Duyarlılık analizi (±%{100 * config['sensitivity']['weight_perturbation']:.0f})",
            "",
            "```",
            sensitivity_table(rows),
            "```",
        ]

    # k-means uyumu bugüne kadar yalnızca konsola basılıyordu. Bir sayının
    # savunulabilmesi için açılacak bir dosyası olmalı.
    if agreement is not None:
        parts += [
            "",
            "## 5. Bağımsız k-means çapraz kontrolü",
            "",
            "Jenks doğal kırılımlarıyla üretilen sınıflar, aynı risk indeksine "
            "bağımsız olarak uygulanan k-means sınıflandırmasıyla "
            f"**%{100 * agreement:.1f}** oranında aynı sınıfı veriyor.",
            "",
            "Jenks tek boyutlu bir optimizasyon, k-means farklı bir amaç fonksiyonu",
            "kullanır; uyumun yüksek çıkması sınıf sınırlarının yöntem seçiminden",
            "değil verinin kendi yapısından geldiğini gösterir.",
        ]

    out.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
