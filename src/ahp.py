"""Adım 4 — AHP (Analytic Hierarchy Process) çekirdeği.

Saaty'nin (1980) yöntemi:
  1. n x n ikili karşılaştırma matrisi (a_ij = i'nin j'ye göre önemi, a_ji = 1/a_ij)
  2. Ağırlıklar = matrisin baskın (principal) özvektörü, toplamı 1'e normalize
  3. Tutarlılık: CI = (lambda_max - n) / (n - 1),  CR = CI / RI(n)
  4. CR > 0.10 ise matris reddedilir (ValueError)

Bu modül konfigürasyondan bağımsız çalışabilir (saf numpy) — birim testleri
bilinen analitik sonuçlarla doğrulanabilsin diye.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Saaty (1980) rastgele tutarlılık indeksi (Random Index), n = 1..10.
# Config'ten okunabilir; burada modülün tek başına çalışabilmesi için varsayılan.
DEFAULT_RANDOM_INDEX = (0.0, 0.0, 0.58, 0.90, 1.12, 1.24, 1.32, 1.41, 1.45, 1.49)
DEFAULT_MAX_CR = 0.10


class InconsistentMatrixError(ValueError):
    """Tutarlılık oranı eşiği aştığında fırlatılır."""


@dataclass(frozen=True)
class AHPResult:
    """AHP çözümünün tüm ara ürünleri (raporlanabilir olsun diye saklanır)."""

    criteria: tuple[str, ...]
    weights: np.ndarray
    lambda_max: float
    consistency_index: float
    consistency_ratio: float
    random_index: float

    @property
    def weight_map(self) -> dict[str, float]:
        return {name: float(w) for name, w in zip(self.criteria, self.weights)}

    def ranked(self) -> list[tuple[str, float]]:
        return sorted(self.weight_map.items(), key=lambda kv: kv[1], reverse=True)

    def summary(self) -> str:
        lines = [f"{'Kriter':<22}{'Ağırlık':>10}"]
        lines.append("-" * 32)
        for name, w in self.ranked():
            lines.append(f"{name:<22}{w:>10.4f}")
        lines.append("-" * 32)
        lines.append(f"{'TOPLAM':<22}{self.weights.sum():>10.4f}")
        lines.append("")
        lines.append(f"lambda_max = {self.lambda_max:.4f}   (n = {len(self.criteria)})")
        lines.append(f"CI         = {self.consistency_index:.4f}")
        lines.append(f"RI         = {self.random_index:.4f}")
        lines.append(f"CR         = {self.consistency_ratio:.4f}")
        return "\n".join(lines)


def validate_matrix(matrix: np.ndarray, *, reciprocal_tol: float = 1e-3) -> np.ndarray:
    """Matrisin AHP için geçerli olup olmadığını kontrol eder.

    Kontroller: kare olması, pozitiflik, köşegenin 1 olması ve karşılıklılık
    (a_ij * a_ji == 1). Karşılıklılık toleransı config'te 4 haneli ondalıklarla
    (ör. 0.3333) yazılan değerlere izin verecek kadar gevşektir.
    """
    m = np.asarray(matrix, dtype=float)
    if m.ndim != 2 or m.shape[0] != m.shape[1]:
        raise ValueError(f"Matris kare olmalı, şekil: {m.shape}")
    if m.shape[0] < 2:
        raise ValueError("En az 2 kriter gerekir")
    if not np.all(np.isfinite(m)):
        raise ValueError("Matriste NaN/Inf var")
    if np.any(m <= 0):
        raise ValueError("Tüm karşılaştırma değerleri pozitif olmalı")
    if not np.allclose(np.diag(m), 1.0, atol=reciprocal_tol):
        raise ValueError("Köşegen elemanları 1 olmalı")

    product = m * m.T
    if not np.allclose(product, 1.0, atol=reciprocal_tol, rtol=reciprocal_tol):
        bad = np.argwhere(~np.isclose(product, 1.0, atol=reciprocal_tol, rtol=reciprocal_tol))
        i, j = bad[0]
        raise ValueError(
            f"Karşılıklılık ihlali: a[{i}][{j}]={m[i, j]:.4f} ile a[{j}][{i}]={m[j, i]:.4f} "
            f"çarpımı {product[i, j]:.4f} (1.0 olmalı)"
        )
    return m


def principal_eigenvector(matrix: np.ndarray) -> tuple[np.ndarray, float]:
    """Baskın özvektörü ve karşılık gelen özdeğeri (lambda_max) döndürür.

    Returns:
        (toplamı 1'e normalize edilmiş ağırlık vektörü, lambda_max)
    """
    m = np.asarray(matrix, dtype=float)
    eigvals, eigvecs = np.linalg.eig(m)

    idx = int(np.argmax(eigvals.real))
    lambda_max = float(eigvals[idx].real)

    vector = np.abs(eigvecs[:, idx].real)
    total = vector.sum()
    if total == 0:
        raise ValueError("Özvektör sıfır toplamlı — matris dejenere")
    return vector / total, lambda_max


def geometric_mean_weights(matrix: np.ndarray) -> np.ndarray:
    """Bağımsız çapraz kontrol: satır geometrik ortalaması yöntemi.

    Tutarlı bir matriste özvektör yöntemiyle birebir aynı sonucu verir;
    farkın büyümesi tutarsızlığın işaretidir.
    """
    m = np.asarray(matrix, dtype=float)
    gm = np.exp(np.log(m).mean(axis=1))
    return gm / gm.sum()


def consistency_ratio(
    lambda_max: float,
    n: int,
    random_index: tuple[float, ...] | list[float] = DEFAULT_RANDOM_INDEX,
) -> tuple[float, float, float]:
    """CI, RI ve CR üçlüsünü döndürür."""
    if n < 3:
        # n <= 2 için tutarsızlık matematiksel olarak mümkün değildir.
        return 0.0, 0.0, 0.0
    ci = (lambda_max - n) / (n - 1)
    try:
        ri = float(random_index[n - 1])
    except IndexError as exc:
        raise ValueError(
            f"n={n} için Random Index tanımlı değil (tablo {len(random_index)} elemanlı)"
        ) from exc
    if ri == 0:
        raise ValueError(f"n={n} için RI sıfır — CR hesaplanamaz")
    return ci, ri, ci / ri


def solve_ahp(
    matrix: np.ndarray,
    criteria: list[str] | tuple[str, ...],
    *,
    max_cr: float = DEFAULT_MAX_CR,
    random_index: tuple[float, ...] | list[float] = DEFAULT_RANDOM_INDEX,
    raise_on_inconsistent: bool = True,
) -> AHPResult:
    """İkili karşılaştırma matrisini çözer ve tutarlılığını denetler.

    Raises:
        InconsistentMatrixError: CR > max_cr ve `raise_on_inconsistent` True ise.
    """
    m = validate_matrix(matrix)
    n = m.shape[0]
    if len(criteria) != n:
        raise ValueError(f"{n}x{n} matris için {n} kriter adı gerekir, {len(criteria)} verildi")

    weights, lambda_max = principal_eigenvector(m)
    ci, ri, cr = consistency_ratio(lambda_max, n, random_index)

    if raise_on_inconsistent and cr > max_cr:
        raise InconsistentMatrixError(
            f"Tutarlılık oranı CR = {cr:.4f} > {max_cr:.2f}. "
            f"(lambda_max={lambda_max:.4f}, CI={ci:.4f}, RI={ri:.2f})\n"
            "İkili karşılaştırma matrisi reddedildi — config.yaml -> ahp.matrix "
            "değerlerini gözden geçirin."
        )

    return AHPResult(
        criteria=tuple(criteria),
        weights=weights,
        lambda_max=lambda_max,
        consistency_index=ci,
        consistency_ratio=cr,
        random_index=ri,
    )


def solve_from_config(config, *, raise_on_inconsistent: bool = True) -> AHPResult:
    """`config.yaml` -> ahp bloğundan AHP çözümünü üretir."""
    ahp_cfg = config["ahp"]
    return solve_ahp(
        np.array(ahp_cfg["matrix"], dtype=float),
        ahp_cfg["criteria_order"],
        max_cr=float(ahp_cfg["consistency"]["max_cr"]),
        random_index=ahp_cfg["consistency"]["random_index"],
        raise_on_inconsistent=raise_on_inconsistent,
    )


def perturb_weights(
    weights: np.ndarray,
    index: int,
    delta: float,
    *,
    renormalize: bool = True,
) -> np.ndarray:
    """Tek bir ağırlığı `delta` oranında değiştirir, kalanları orantılı düzeltir.

    Ör. delta=+0.10 -> w_i %10 artar; diğer ağırlıklar toplamı 1 olacak şekilde
    kendi aralarındaki oranı koruyarak küçültülür.
    """
    w = np.asarray(weights, dtype=float).copy()
    if not 0 <= index < w.size:
        raise IndexError(f"index {index} geçersiz (n={w.size})")

    new_wi = w[index] * (1.0 + delta)
    if new_wi <= 0:
        raise ValueError(f"delta={delta} ağırlığı sıfır/negatif yapıyor")

    if not renormalize:
        w[index] = new_wi
        return w

    others = np.delete(np.arange(w.size), index)
    remaining = 1.0 - new_wi
    if remaining <= 0:
        raise ValueError(f"delta={delta} tek kritere tüm ağırlığı veriyor")

    others_sum = w[others].sum()
    w[others] = w[others] / others_sum * remaining
    w[index] = new_wi
    return w


def sensitivity_weight_sets(
    result: AHPResult,
    perturbation: float = 0.10,
    *,
    renormalize: bool = True,
) -> dict[str, np.ndarray]:
    """Duyarlılık analizi için ağırlık senaryoları üretir.

    Her kriter için +p ve -p olmak üzere 2n senaryo, artı `baseline`.
    Adım 4'te bu ağırlık setlerinin her biriyle risk haritası yeniden
    hesaplanıp sonuç haritasının ne kadar değiştiği ölçülür.
    """
    sets: dict[str, np.ndarray] = {"baseline": result.weights.copy()}
    for i, name in enumerate(result.criteria):
        for sign, tag in ((+1, "plus"), (-1, "minus")):
            key = f"{name}_{tag}{int(perturbation * 100)}"
            sets[key] = perturb_weights(
                result.weights, i, sign * perturbation, renormalize=renormalize
            )
    return sets
