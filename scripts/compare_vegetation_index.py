"""Bitki örtüsü indeksi seçiminin risk haritasına etkisi (NDVI vs EVI).

Jia ve ark. (2020, IJERPH 17:7660) EVI'nin kuraklık duyarlılığını göstermede
NDVI'dan bir miktar daha başarılı olduğunu buluyor (R² 0.61 vs 0.59). Bu betik
soruyu bu havza için doğrudan sınar: **indeks seçimi haritayı değiştiriyor mu,
ve değiştiriyorsa hangisi bağımsız ölçümle daha uyumlu?**

Kullanım:
    python -m scripts.compare_vegetation_index

Ön koşul: her iki kurak dönem kompoziti de üretilmiş olmalı.
    python -m scripts.step02_fetch_data --only ndvi-dry
    python -c "...fetch_ndvi_dry_composite(cfg, grid, index='evi')"

Çıktı: outputs/reports/vegetation_index_comparison.md
"""

from __future__ import annotations

import argparse

import numpy as np

from src.ahp import solve_from_config
from src.classify import apply_breaks, classify_risk
from src.config import load_config
from src.criteria.normalize import normalize_criterion
from src.fetch.common import interim_path, resolve
from src.grid import build_grid, read_grid_aligned
from src.overlay import load_criteria, weighted_overlay
from src.validate import et_ratio, et_ratio_by_class, rank_correlation

INDICES = ("ndvi", "evi")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NDVI ve EVI karşılaştırması")
    parser.add_argument("--config", default=None)
    parser.add_argument("--report", default="outputs/reports/vegetation_index_comparison.md")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    grid = build_grid(config)

    missing = [i for i in INDICES if not interim_path(config, f"{i}_dry.tif").exists()]
    if missing:
        raise SystemExit(
            f"Eksik kompozit: {[f'{i}_dry.tif' for i in missing]}. "
            "Önce her iki indeksi de üretin."
        )

    print("=" * 68)
    print("BİTKİ ÖRTÜSÜ İNDEKSİ KARŞILAŞTIRMASI — NDVI vs EVI")
    print("=" * 68)

    spec = config.criterion("ndvi_dry")
    result = solve_from_config(config)
    stack = load_criteria(config, grid)
    vi_position = list(stack.names).index("ndvi_dry")

    ratio = et_ratio(config, grid)
    raw, scores, risks, classes = {}, {}, {}, {}

    for index in INDICES:
        array = read_grid_aligned(interim_path(config, f"{index}_dry.tif"), grid).astype("float32")
        raw[index] = np.where(array == np.float32(config.nodata), np.nan, array)
        scores[index] = normalize_criterion(raw[index], spec, name=index)

        # Yalnızca bu katmanı değiştirip aynı ağırlıklarla yeniden çakıştır.
        swapped = stack.data.copy()
        swapped[vi_position] = scores[index]
        mask = ~np.isnan(swapped).any(axis=0)
        risks[index] = weighted_overlay(
            type(stack)(names=stack.names, data=swapped, valid_mask=mask), result.weights
        )
        classes[index], _ = classify_risk(config, risks[index])

    lines = _report(config, grid, raw, scores, risks, classes, ratio)
    print("\n" + lines)

    out = resolve(config["paths"]["reports"]) / "vegetation_index_comparison.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "# Bitki örtüsü indeksi karşılaştırması — NDVI vs EVI\n\n```\n" + lines + "\n```\n",
        encoding="utf-8",
    )
    print(f"\nRapor: {out.relative_to(out.parents[2])}")
    return 0


def _report(config, grid, raw, scores, risks, classes, ratio) -> str:
    lines = ["HAM İNDEKS DEĞERLERİ", "-" * 68]
    for index in INDICES:
        finite = raw[index][np.isfinite(raw[index])]
        lines.append(
            f"  {index.upper():<5} {finite.min():+.3f} .. {finite.max():+.3f}  "
            f"medyan {np.median(finite):+.3f}  ort {finite.mean():+.3f}  "
            f"std {finite.std():.3f}"
        )

    both = np.isfinite(raw["ndvi"]) & np.isfinite(raw["evi"])
    lines += [
        "",
        f"  Ham katmanlar arası Pearson r  : {np.corrcoef(raw['ndvi'][both], raw['evi'][both])[0, 1]:.4f}",
        f"  Ham katmanlar arası Spearman ρ : {rank_correlation(raw['ndvi'], raw['evi']):.4f}",
        "",
        "RİSK HARİTASINA ETKİSİ",
        "-" * 68,
    ]

    valid = np.isfinite(risks["ndvi"]) & np.isfinite(risks["evi"])
    diff = np.abs(risks["ndvi"][valid] - risks["evi"][valid])
    agreement = float((classes["ndvi"][valid] == classes["evi"][valid]).mean())
    within_one = float(
        (np.abs(classes["ndvi"][valid].astype(int) - classes["evi"][valid].astype(int)) <= 1).mean()
    )

    lines += [
        f"  Risk indeksi ortalama farkı : {diff.mean():.5f}",
        f"  Risk indeksi maksimum farkı : {diff.max():.5f}",
        f"  Aynı sınıfta kalan piksel   : %{100 * agreement:.2f}",
        f"  En fazla 1 sınıf kayan      : %{100 * within_one:.2f}",
    ]

    if ratio is None:
        lines += ["", "ET/PET katmanı yok — bağımsız karşılaştırma atlandı."]
        return "\n".join(lines)

    lines += [
        "",
        "BAĞIMSIZ ÖLÇÜMLE UYUM (MODIS ET/PET)",
        "-" * 68,
        "  Hangi indeksin ürettiği harita, modele hiç girmemiş buharlaşma",
        "  oranıyla daha tutarlı? Daha güçlü (mutlak değerce büyük) negatif",
        "  korelasyon daha iyidir.",
        "",
    ]

    for index in INDICES:
        rho_layer = rank_correlation(raw[index], ratio)
        rho_risk = rank_correlation(risks[index], ratio)
        rows = et_ratio_by_class(classes[index], ratio, config["classification"]["n_classes"])
        spread = rows[0][1] - rows[-1][1] if len(rows) >= 2 else float("nan")
        monotone = all(rows[i][1] >= rows[i + 1][1] for i in range(len(rows) - 1))
        lines.append(
            f"  {index.upper():<5} ham katman ρ = {rho_layer:+.4f} | "
            f"risk haritası ρ = {rho_risk:+.4f} | "
            f"sınıf 1-5 ET/PET farkı = {spread:.4f} | "
            f"monoton: {'evet' if monotone else 'HAYIR'}"
        )

    better = max(INDICES, key=lambda i: abs(rank_correlation(risks[i], ratio)))
    lines += [
        "",
        f"  Bağımsız ölçümle daha uyumlu: {better.upper()}",
        "",
        "  NOT: Fark küçükse indeks seçimi bu havzada belirleyici değildir;",
        "  bu da raporlanmaya değer bir sonuçtur.",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
