"""Kriter katmanlarının 0-1 risk skoruna normalize edilmesi (Adım 3).

Sözleşme: her yöntem, çıktısında **1 = en yüksek kuraklık riski**, **0 = en
düşük** olacak şekilde bir dizi döndürür. Geçersiz pikseller NaN kalır.

Yön çevirmesi tek bir yerde yapılır: `higher_is_riskier: false` olan kriterler
(yağış, NDVI) ölçeklendikten sonra `1 - x` ile ters çevrilir. Bu mantığın koda
dağılması, işaret hatalarının en sık kaynağıdır.

Eşikler ve yöntem adları config.yaml'dan gelir; burada hiçbir sayı sabit
değildir.
"""

from __future__ import annotations

import numpy as np

METHODS = ("minmax_percentile", "minmax_capped", "lookup", "none")


class NormalizationError(ValueError):
    """Kriter tanımı ile veri uyuşmadığında fırlatılır."""


def normalize_criterion(array: np.ndarray, spec: dict, *, name: str = "?") -> np.ndarray:
    """Ham kriter değerlerini 0-1 risk skoruna çevirir.

    Args:
        array: Ham değerler; geçersiz pikseller NaN olmalı.
        spec: config.yaml -> criteria.<ad> bloğu.
        name: Hata mesajlarında görünecek kriter adı.
    """
    method = spec.get("normalization")
    if method not in METHODS:
        raise NormalizationError(f"{name}: bilinmeyen normalizasyon '{method}'. Seçenekler: {METHODS}")
    if "higher_is_riskier" not in spec:
        raise NormalizationError(f"{name}: `higher_is_riskier` tanımlı değil")

    data = np.asarray(array, dtype="float64")
    if not np.isfinite(data).any():
        raise NormalizationError(f"{name}: katmanda tek bir geçerli piksel yok")

    if method == "minmax_percentile":
        scaled = _minmax_percentile(data, spec, name)
    elif method == "minmax_capped":
        scaled = _minmax_capped(data, spec, name)
    else:  # "lookup" ve "none": değerler zaten 0-1 aralığında
        scaled = _passthrough(data, name)

    if not spec["higher_is_riskier"]:
        scaled = 1.0 - scaled

    return _validated(scaled, name)


def _minmax_percentile(data: np.ndarray, spec: dict, name: str) -> np.ndarray:
    """Uç değerleri yüzdeliklerle kırpıp doğrusal ölçekler.

    Ham min/max yerine yüzdelik kullanılır: tek bir aykırı piksel (bulut
    artefaktı, veri hatası) tüm ölçeği ezmesin diye.
    """
    lo_pct, hi_pct = spec.get("percentile_clip", [2, 98])
    if not 0 <= lo_pct < hi_pct <= 100:
        raise NormalizationError(f"{name}: geçersiz percentile_clip {[lo_pct, hi_pct]}")

    finite = data[np.isfinite(data)]
    lo, hi = np.percentile(finite, [lo_pct, hi_pct])

    if hi <= lo:
        raise NormalizationError(
            f"{name}: %{lo_pct} ve %{hi_pct} yüzdelikleri eşit ({lo:.6g}) — "
            "katman sabit görünüyor, kriter ayrım üretmez"
        )

    return np.clip((data - lo) / (hi - lo), 0.0, 1.0)


def _minmax_capped(data: np.ndarray, spec: dict, name: str) -> np.ndarray:
    """0 ile bir tavan değeri arasında ölçekler; tavanın ötesi doygunlaşır.

    Su kaynağına mesafe için: 15 km'nin ötesinde "daha da uzak olmak" pratikte
    ek risk getirmez, bu yüzden doğrusal ölçek yerine doygunluk kullanılır.
    """
    cap = spec.get("cap_value_m")
    if cap is None or cap <= 0:
        raise NormalizationError(f"{name}: minmax_capped için pozitif `cap_value_m` gerekir")
    return np.clip(data / float(cap), 0.0, 1.0)


def _passthrough(data: np.ndarray, name: str) -> np.ndarray:
    """Zaten 0-1 olması gereken katmanları doğrular ve olduğu gibi geçirir."""
    finite = data[np.isfinite(data)]
    if finite.min() < -1e-6 or finite.max() > 1 + 1e-6:
        raise NormalizationError(
            f"{name}: 'lookup'/'none' yöntemi 0-1 aralığı bekler, "
            f"bulunan aralık [{finite.min():.4g}, {finite.max():.4g}]"
        )
    return np.clip(data, 0.0, 1.0)


def _validated(scaled: np.ndarray, name: str) -> np.ndarray:
    finite = scaled[np.isfinite(scaled)]
    if finite.size == 0:
        raise NormalizationError(f"{name}: normalizasyon sonrası geçerli piksel kalmadı")
    if finite.min() < -1e-9 or finite.max() > 1 + 1e-9:
        raise NormalizationError(
            f"{name}: normalize edilmiş değerler 0-1 dışında "
            f"[{finite.min():.6g}, {finite.max():.6g}]"
        )
    return scaled.astype("float32")


def describe(array: np.ndarray) -> str:
    """Normalize edilmiş katman için tek satırlık özet (log çıktısı)."""
    finite = array[np.isfinite(array)]
    return (
        f"ort {finite.mean():.3f}  medyan {np.median(finite):.3f}  "
        f"p10 {np.percentile(finite, 10):.3f}  p90 {np.percentile(finite, 90):.3f}  "
        f"maskeli %{100 * (1 - finite.size / array.size):.2f}"
    )
