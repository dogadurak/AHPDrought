"""Anomali izleme modülünün testleri (Modül 1).

Buradaki asıl mesele **dışarıda-bırakmalı taban çizgisi**: hedef yıl kendi
taban çizgisine dahil edilirse anomali sistematik olarak küçük çıkar. 6 yıllık
bir tabanda bu etki büyüktür ve fark edilmesi zordur — sonuç hata vermez,
sadece "her şey normal" der.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.config import load_config
from src.monitor import ANOMALY_CLASSES, AnomalyResult


@pytest.fixture
def config():
    return load_config()


def make_result(z: np.ndarray, year: int = 2024, baseline=(2019, 2020, 2021, 2022, 2023)):
    return AnomalyResult(year=year, z_score=z.astype("float32"),
                         baseline_years=baseline, index_name="ndvi")


# --- Dışarıda-bırakmalı taban çizgisinin gerekçesi ---------------------------


def leave_one_out_z(values: np.ndarray, target_index: int) -> float:
    others = np.delete(values, target_index)
    return (values[target_index] - others.mean()) / others.std(ddof=1)


def naive_z(values: np.ndarray, target_index: int) -> float:
    return (values[target_index] - values.mean()) / values.std(ddof=1)


def test_leave_one_out_gives_a_larger_anomaly_than_naive():
    """Hedef yıl kendi tabanına dahil edilirse anomali KÜÇÜLÜR.

    Bu test kodu değil yöntemi doğrular: 6 yıllık bir tabanda hedef yıl
    ortalamanın altıda birini belirler, yani kendi sapmasını kendisi bastırır.
    """
    values = np.array([0.50, 0.52, 0.48, 0.51, 0.49, 0.30])  # son yıl kurak
    target = 5

    loo = leave_one_out_z(values, target)
    naive = naive_z(values, target)

    assert loo < naive < 0, f"loo={loo:.3f} naive={naive:.3f}"
    assert abs(loo) > abs(naive) * 1.3, (
        "dışarıda bırakma, anomaliyi belirgin şekilde büyütmeliydi — "
        f"loo={loo:.2f}, naive={naive:.2f}"
    )


def test_naive_baseline_can_hide_a_real_anomaly():
    """Küçük tabanda naif z-skoru eşiğin altında kalabilir."""
    values = np.array([0.50, 0.52, 0.48, 0.51, 0.49, 0.34])
    assert naive_z(values, 5) > -2.0      # naif: "şiddetli değil"
    assert leave_one_out_z(values, 5) < -2.5  # gerçek: olağanüstü


# --- Sonuç nesnesinin davranışı ----------------------------------------------


def test_class_shares_sum_to_one():
    rng = np.random.default_rng(0)
    result = make_result(rng.normal(0, 1, (200, 200)))
    total = sum(share for _, share in result.class_shares())
    assert total == pytest.approx(1.0, abs=1e-9)


def test_standard_normal_input_lands_mostly_near_normal():
    """N(0,1) girdide alanın çoğu 'normale yakın' ve komşu sınıflarda olmalı."""
    rng = np.random.default_rng(1)
    result = make_result(rng.normal(0, 1, (300, 300)))
    shares = dict(result.class_shares())

    assert shares["Normale yakın"] == pytest.approx(0.383, abs=0.02)  # ±0.5 sigma
    assert shares["Olağanüstü altında"] < 0.03


def test_shifted_distribution_moves_into_dry_classes():
    rng = np.random.default_rng(2)
    result = make_result(rng.normal(-1.5, 1, (300, 300)))
    shares = dict(result.class_shares())

    dry = sum(v for k, v in shares.items() if "altında" in k)
    assert dry > 0.75, f"kurak sınıfların payı %{100 * dry:.0f}, daha yüksek olmalıydı"


def test_nan_pixels_are_excluded_not_counted_as_normal():
    z = np.full((10, 10), np.nan)
    z[:5, :] = 0.0
    result = make_result(z)

    shares = dict(result.class_shares())
    assert shares["Normale yakın"] == pytest.approx(1.0), "NaN'lar 'normal' sayılmamalı"


def test_summary_reports_the_baseline_years():
    result = make_result(np.zeros((5, 5)))
    text = result.summary()
    assert "hedef yıl dışarıda" in text
    assert "2019" in text and "2024" not in text.split("taban çizgisi")[1].split("\n")[0]


# --- Sınıf tanımları ---------------------------------------------------------


def test_anomaly_classes_are_contiguous_and_ordered():
    """Sınıflar boşluksuz ve örtüşmesiz olmalı, yoksa piksel kaybolur."""
    bounds = [(low, high) for low, high, _ in ANOMALY_CLASSES]
    for (_, high), (next_low, _) in zip(bounds, bounds[1:]):
        assert high == next_low, f"sınıf sınırlarında boşluk/örtüşme: {high} -> {next_low}"

    assert bounds[0][0] == -np.inf
    assert bounds[-1][1] == np.inf


def test_anomaly_thresholds_match_spi_convention():
    """Anomali eşikleri SPI sınıflarıyla aynı olmalı — iki ölçek birlikte okunuyor."""
    from src.drought_index import SPI_CATEGORIES

    anomaly_bounds = {low for low, _, _ in ANOMALY_CLASSES if np.isfinite(low)}
    spi_bounds = {low for low, _, _ in SPI_CATEGORIES if np.isfinite(low)}
    assert anomaly_bounds <= spi_bounds, (
        f"anomali eşikleri SPI'da yok: {anomaly_bounds - spi_bounds}"
    )


# --- Konfigürasyon tutarlılığı -----------------------------------------------


def test_baseline_has_enough_years(config):
    from src.monitor import MIN_BASELINE_YEARS

    years = config["periods"]["reference_years"]
    assert len(years) - 1 >= MIN_BASELINE_YEARS, (
        f"{len(years)} referans yılı var; bir yıl hedef olarak dışlanınca "
        f"taban çizgisi {len(years) - 1} yıla iniyor, en az {MIN_BASELINE_YEARS} gerekir"
    )
