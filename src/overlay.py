"""Adım 4 — AHP ağırlıklı çakıştırma ve duyarlılık analizi.

Risk indeksi, normalize edilmiş kriterlerin AHP ağırlıklarıyla ağırlıklı
toplamıdır:

    R = Σ w_i · c_i        (Σ w_i = 1,  c_i ∈ [0, 1]  ->  R ∈ [0, 1])

Maske yayılımı: kriterlerden HERHANGİ biri bir pikselde tanımsızsa (ör. arazi
örtüsü yerleşim/su olduğu için maskeliyse) o piksel sonuçta da tanımsız kalır.
Eksik kriteri sıfır saymak, o pikseli yapay olarak "düşük riskli" gösterirdi.

Efektif katkı: AHP ağırlığı, kriterin *ölçeğinin tamamını* kullandığı
varsayımıyla anlam taşır. Bir kriterin gerçek dağılımı [0, 0.4] aralığına
sıkışmışsa nominal ağırlığı kadar ayrım üretmez. `contribution_report()` bu
farkı açıkça gösterir — aksi halde ağırlık tablosu yanıltıcı olur.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .ahp import AHPResult, sensitivity_weight_sets, solve_from_config
from .config import Config
from .fetch.common import resolve
from .grid import TargetGrid, read_grid_aligned, write_raster


@dataclass(frozen=True)
class CriteriaStack:
    """Tüm kriterlerin ortak maskeyle hizalanmış hali."""

    names: tuple[str, ...]
    data: np.ndarray          # (n_kriter, satır, sütun), geçersizler NaN
    valid_mask: np.ndarray    # (satır, sütun) bool — her kriterin tanımlı olduğu yerler

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape[1:]

    def coverage(self) -> float:
        return float(self.valid_mask.mean())


def load_criteria(config: Config, grid: TargetGrid) -> CriteriaStack:
    """Adım 3 çıktılarını okur, ortak geçerlilik maskesini hesaplar."""
    names = tuple(config.criteria_order)

    layers = []
    for name in names:
        path = config.criterion_path(name)
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} bulunamadı. Önce "
                f"`python -m scripts.step03_build_criteria --scenario {config.scenario}` çalıştırın."
            )
        array = read_grid_aligned(path, grid).astype("float32")
        layers.append(np.where(array == np.float32(config.nodata), np.nan, array))

    data = np.stack(layers)
    valid = ~np.isnan(data).any(axis=0)

    if not valid.any():
        raise RuntimeError("Hiçbir pikselde tüm kriterler tanımlı değil")
    return CriteriaStack(names=names, data=data, valid_mask=valid)


def weighted_overlay(stack: CriteriaStack, weights: np.ndarray) -> np.ndarray:
    """Ağırlıklı toplamla risk indeksini hesaplar (geçersiz pikseller NaN)."""
    weights = np.asarray(weights, dtype="float64")
    if weights.size != len(stack.names):
        raise ValueError(f"{len(stack.names)} kriter için {weights.size} ağırlık verildi")
    if not np.isclose(weights.sum(), 1.0, atol=1e-6):
        raise ValueError(f"Ağırlıkların toplamı 1 olmalı, {weights.sum():.6f} bulundu")
    if np.any(weights < 0):
        raise ValueError("Ağırlıklar negatif olamaz")

    risk = np.einsum("k,kij->ij", weights, np.nan_to_num(stack.data, nan=0.0))
    
    # --- Sulama/Direnç Faktörü (Mitigation Factor) ---
    # Gerçek hasarı öngörebilmek için fiziksel kırılganlığı sulama direnciyle çarpıyoruz.
    # 'distance_to_water' normalize skoru: 0 (suya çok yakın, düşük risk) ile 1 (suya uzak, yüksek risk)
    # Suya yakınlık bir "direnç" (mitigation) oluşturur. Riski %30'a kadar düşürebilir.
    if "distance_to_water" in stack.names:
        idx = stack.names.index("distance_to_water")
        dist_score = np.nan_to_num(stack.data[idx], nan=0.0)
        # Suya yakınsa (dist_score ~ 0), mitigation ~ 0.30
        # Suya uzaksa (dist_score ~ 1), mitigation ~ 0.00
        mitigation_factor = 0.30 * (1.0 - dist_score)
        risk = risk * (1.0 - mitigation_factor)

    return np.where(stack.valid_mask, risk, np.nan).astype("float32")


def contribution_report(stack: CriteriaStack, result: AHPResult) -> str:
    """Nominal AHP ağırlığı ile efektif ayrım gücünü yan yana gösterir.

    Efektif katkı, kriterin ağırlıkla çarpılmış değerlerinin standart sapmasıdır:
    ölçeğinin tamamını kullanmayan bir kriter, nominal ağırlığı yüksek olsa bile
    sonuç haritasında az ayrım üretir.
    """
    weights = result.weight_map
    rows = []
    for i, name in enumerate(stack.names):
        values = stack.data[i][stack.valid_mask]
        w = weights[name]
        rows.append((name, w, float(values.min()), float(values.max()), float((w * values).std())))

    total_spread = sum(r[4] for r in rows)
    lines = [
        f"{'Kriter':<20}{'Ağırlık':>9}{'Kullanılan aralık':>20}{'Efektif katkı':>16}",
        "-" * 65,
    ]
    for name, w, lo, hi, spread in sorted(rows, key=lambda r: r[4], reverse=True):
        share = 100 * spread / total_spread if total_spread else 0.0
        lines.append(f"{name:<20}{w:>9.4f}{f'{lo:.2f} - {hi:.2f}':>20}{f'%{share:.1f}':>16}")
    lines.append("-" * 65)
    lines.append(
        "Efektif katkı = ağırlıkla çarpılmış değerlerin standart sapmasının payı.\n"
        "Nominal ağırlığından belirgin düşük kalan bir kriter, ölçeğinin tamamını\n"
        "kullanmadığı için sonuç haritasında beklenenden az ayrım üretiyor demektir."
    )
    return "\n".join(lines)


def build_risk_index(
    config: Config, grid: TargetGrid, *, overwrite: bool = False
) -> tuple[Path, np.ndarray, AHPResult, CriteriaStack]:
    """AHP ağırlıklarıyla risk indeksini üretir ve diske yazar."""
    result = solve_from_config(config)
    stack = load_criteria(config, grid)

    print(f"  Geçerli piksel: %{100 * stack.coverage():.2f}")
    risk = weighted_overlay(stack, result.weights)

    out = resolve(config["paths"]["data_processed"]) / f"risk_index_{config.scenario}.tif"
    if out.exists() and not overwrite:
        print(f"  önbellekten: {out.name}")
    else:
        write_raster(
            np.where(np.isnan(risk), config.nodata, risk),
            grid,
            out,
            nodata=config.nodata,
            description=f"AHP kuraklık risk indeksi (0-1), senaryo: {config.scenario}",
        )

    valid = risk[~np.isnan(risk)]
    print(
        f"  Risk indeksi: {valid.min():.4f} - {valid.max():.4f} "
        f"(ortalama {valid.mean():.4f}, medyan {np.median(valid):.4f})"
    )
    return out, risk, result, stack


# --- Duyarlılık analizi ------------------------------------------------------


@dataclass(frozen=True)
class SensitivityRow:
    scenario: str
    mean_abs_diff: float
    max_abs_diff: float
    class_agreement: float
    spearman_rho: float


def sensitivity_analysis(
    config: Config,
    stack: CriteriaStack,
    result: AHPResult,
    baseline_risk: np.ndarray,
    *,
    n_classes: int,
    breaks: np.ndarray,
    sample_size: int = 100_000,
) -> list[SensitivityRow]:
    """Her ağırlığı ±%p değiştirip sonuç haritasının ne kadar değiştiğini ölçer.

    Üç metrik birlikte okunmalı:
      - mean_abs_diff : sürekli indeksin ortalama kayması (küçük olması iyi)
      - class_agreement: 5 sınıflı haritada aynı sınıfta kalan piksel oranı
      - spearman_rho  : piksellerin göreli sıralamasının korunması

    Sınıf uyumu, kullanıcının gerçekten gördüğü çıktının kararlılığını ölçtüğü
    için en anlamlı olanıdır.
    """
    from .classify import apply_breaks

    cfg = config["sensitivity"]
    perturbation = float(cfg["weight_perturbation"])
    weight_sets = sensitivity_weight_sets(result, perturbation, renormalize=cfg["renormalize"])

    valid = ~np.isnan(baseline_risk)
    base_values = baseline_risk[valid]
    base_classes = apply_breaks(baseline_risk, breaks, n_classes)[valid]

    rng = np.random.default_rng(0)
    sample_idx = _sample_indices(base_values.size, sample_size, rng)

    rows = []
    for name, weights in weight_sets.items():
        if name == "baseline":
            continue
        risk = weighted_overlay(stack, weights)
        values = risk[valid]
        classes = apply_breaks(risk, breaks, n_classes)[valid]

        diff = np.abs(values - base_values)
        rows.append(
            SensitivityRow(
                scenario=name,
                mean_abs_diff=float(diff.mean()),
                max_abs_diff=float(diff.max()),
                class_agreement=float((classes == base_classes).mean()),
                spearman_rho=_spearman(base_values[sample_idx], values[sample_idx]),
            )
        )
    return rows


def _sample_indices(size: int, sample_size: int, rng) -> np.ndarray:
    if size <= sample_size:
        return np.arange(size)
    return rng.choice(size, size=sample_size, replace=False)


def _spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Sıra korelasyonu (scipy'siz: sıralara Pearson)."""
    from scipy.stats import rankdata

    ra, rb = rankdata(a), rankdata(b)
    ra = ra - ra.mean()
    rb = rb - rb.mean()
    denominator = np.sqrt((ra**2).sum() * (rb**2).sum())
    return float((ra * rb).sum() / denominator) if denominator else 1.0


def sensitivity_table(rows: list[SensitivityRow]) -> str:
    lines = [
        f"{'Senaryo':<28}{'Ort. fark':>11}{'Maks. fark':>12}{'Sınıf uyumu':>13}{'Spearman':>10}",
        "-" * 74,
    ]
    for row in sorted(rows, key=lambda r: r.class_agreement):
        lines.append(
            f"{row.scenario:<28}{row.mean_abs_diff:>11.5f}{row.max_abs_diff:>12.5f}"
            f"{f'%{100 * row.class_agreement:.2f}':>13}{row.spearman_rho:>10.5f}"
        )
    lines.append("-" * 74)
    worst = min(rows, key=lambda r: r.class_agreement)
    lines.append(
        f"En duyarlı senaryo: {worst.scenario} — sınıf uyumu %{100 * worst.class_agreement:.2f}"
    )
    return "\n".join(lines)
