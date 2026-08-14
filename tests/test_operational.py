"""Çok yıllı operasyonel sınamanın testleri.

Sınanan şey, sınamanın kendisi: kurak yıl etiketi doğru mu konuyor, havuzlama
ağırlıklı mı, ve hüküm cümlesi olumsuz sonucu gizlemiyor mu?
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.operational import OperationalTest, YearOutcome, label_dry_years, pooled_class_means


def outcome(year: int, spi: float, is_dry: bool, rho: float, class_means=None) -> YearOutcome:
    return YearOutcome(
        year=year, spi=spi, is_dry=is_dry, mean_anomaly=-0.2,
        rank_correlation=rho,
        class_means=class_means or [(c, -0.1 * c, 1000) for c in range(1, 6)],
        monotone=True,
    )


# --- Kurak yıl etiketi -------------------------------------------------------


def test_summer_spi_labelling_uses_summer_months():
    index = pd.date_range("2017-01", periods=9 * 12, freq="MS")
    series = pd.Series(0.0, index=index)
    for year in (2019, 2022):
        mask = (series.index.year == year) & (series.index.month.isin([7, 8, 9]))
        series[mask] = -1.5

    labels = label_dry_years(series, list(range(2017, 2026)),
                             method="summer_spi", threshold=-0.5)
    assert {y for y, (_, d) in labels.items() if d} == {2019, 2022}


def test_spring_soil_labelling_standardises_across_years():
    """İlkbahar toprak nemi mutlak değil, kendi dağılımına göre değerlendirilir."""
    index = pd.date_range("2017-01", periods=9 * 12, freq="MS")
    series = pd.Series(100.0, index=index)
    # 2019 ve 2024 ilkbaharlarını belirgin kuru yap
    for year in (2019, 2024):
        mask = (series.index.year == year) & (series.index.month.isin([3, 4]))
        series[mask] = 40.0

    labels = label_dry_years(series, list(range(2017, 2026)),
                             method="spring_soil", threshold=-0.5)
    assert {y for y, (_, d) in labels.items() if d} == {2019, 2024}


def test_wet_season_labelling_shifts_november_december_forward():
    """Kasım-aralık yağışı BİR SONRAKİ yazı besler."""
    index = pd.date_range("2016-11", periods=10 * 12, freq="MS")
    series = pd.Series(50.0, index=index)
    # 2018 su yılını kurut: Kas-Ara 2017 + Oca-Nis 2018
    dry = (((series.index.year == 2017) & (series.index.month >= 11))
           | ((series.index.year == 2018) & (series.index.month <= 4)))
    series[dry] = 5.0

    labels = label_dry_years(series, list(range(2017, 2026)),
                             method="wet_season_precip", threshold=-0.5)
    assert labels[2018][1] is True


def test_unknown_labelling_method_is_rejected():
    index = pd.date_range("2020-01", periods=24, freq="MS")
    with pytest.raises(ValueError, match="Bilinmeyen etiketleme"):
        label_dry_years(pd.Series(1.0, index=index), [2020], method="sihir")


def test_threshold_controls_the_labelling():
    index = pd.date_range("2020-01", periods=24, freq="MS")
    series = pd.Series(-0.6, index=index)

    lenient = label_dry_years(series, [2020, 2021], method="summer_spi", threshold=-0.5)
    strict = label_dry_years(series, [2020, 2021], method="summer_spi", threshold=-1.0)

    assert all(is_dry for _, is_dry in lenient.values())
    assert not any(is_dry for _, is_dry in strict.values())


def test_missing_year_is_not_labelled_dry():
    index = pd.date_range("2020-01", periods=12, freq="MS")
    labels = label_dry_years(pd.Series(-2.0, index=index), [2020, 2099], method="summer_spi")
    assert labels[2099][1] is False
    assert not np.isfinite(labels[2099][0])


# --- Havuzlama ---------------------------------------------------------------


def test_pooling_is_weighted_by_pixel_count():
    """Az pikselli bir yıl, çok pikselli yılla eşit ağırlık almamalı."""
    a = outcome(2019, -1.0, True, -0.3, class_means=[(1, -1.0, 10)])
    b = outcome(2022, -1.0, True, -0.3, class_means=[(1, 0.0, 990)])
    test = OperationalTest(outcomes=[a, b], dry_threshold=-0.5)

    pooled = dict(pooled_class_means(test, dry_only=True))
    # Ağırlıklı ortalama: (-1*10 + 0*990) / 1000 = -0.01
    assert pooled[1] == pytest.approx(-0.01)
    # Ağırlıksız olsaydı -0.5 çıkardı
    assert pooled[1] != pytest.approx(-0.5)


def test_pooling_can_include_all_years():
    dry = outcome(2019, -1.0, True, -0.3, class_means=[(1, -1.0, 100)])
    wet = outcome(2020, 0.5, False, -0.05, class_means=[(1, 1.0, 100)])
    test = OperationalTest(outcomes=[dry, wet], dry_threshold=-0.5)

    assert dict(pooled_class_means(test, dry_only=True))[1] == pytest.approx(-1.0)
    assert dict(pooled_class_means(test, dry_only=False))[1] == pytest.approx(0.0)


def test_pooling_with_no_dry_years_returns_empty():
    test = OperationalTest(outcomes=[outcome(2020, 0.5, False, -0.1)], dry_threshold=-0.5)
    assert pooled_class_means(test, dry_only=True) == []


# --- Hüküm ------------------------------------------------------------------


def test_verdict_supports_hypothesis_when_dry_years_are_stronger():
    dry = [outcome(2019, -1.5, True, -0.45), outcome(2022, -1.2, True, -0.38),
           outcome(2017, -1.1, True, -0.42)]
    wet = [outcome(2020, 0.4, False, -0.05), outcome(2021, 0.8, False, +0.02)]
    test = OperationalTest(outcomes=dry + wet, dry_threshold=-0.5)

    assert "DESTEKLENDİ" in test.summary()


def test_verdict_rejects_when_dry_and_wet_are_similar():
    """Kurak ve yağışlı yıllarda ilişki aynıysa harita stresi ayırt etmiyordur."""
    dry = [outcome(y, -1.5, True, -0.20) for y in (2017, 2018, 2019)]
    wet = [outcome(2020, 0.4, False, -0.20)]
    test = OperationalTest(outcomes=dry + wet, dry_threshold=-0.5)

    assert "DESTEKLENMEDİ" in test.summary()
    assert "ayırt etmiyor" in test.summary()


def test_verdict_rejects_when_correlation_has_the_wrong_sign():
    """Kurak yılda ilişki pozitifse harita ters çalışıyordur — gizlenmemeli."""
    dry = [outcome(y, -1.5, True, +0.30) for y in (2017, 2018, 2019)]
    wet = [outcome(2020, 0.4, False, +0.10)]
    test = OperationalTest(outcomes=dry + wet, dry_threshold=-0.5)

    summary = test.summary()
    assert "DESTEKLENMEDİ" in summary
    assert "fiilen sıfır" in summary


def test_verdict_refuses_to_decide_with_too_few_dry_years():
    """Regresyon: tek kurak yılla 'DESTEKLENDİ' hükmü veriliyordu."""
    dry = [outcome(2025, -1.5, True, -0.04)]
    wet = [outcome(y, 0.4, False, -0.01) for y in range(2017, 2025)]
    summary = OperationalTest(outcomes=dry + wet, dry_threshold=-0.5).summary()

    assert "KARAR VERİLEMEZ" in summary
    assert "DESTEKLENDİ" not in summary


def test_verdict_rejects_effect_sizes_below_the_floor():
    """Milyonlarca pikselde 'anlamlı' ama pratikte sıfır olan farklar."""
    dry = [outcome(y, -1.5, True, -0.05) for y in (2017, 2018, 2019)]
    wet = [outcome(2020, 0.4, False, -0.04)]
    assert "DESTEKLENMEDİ" in OperationalTest(outcomes=dry + wet, dry_threshold=-0.5).summary()


def test_summary_reports_group_sizes_when_comparison_impossible():
    test = OperationalTest(outcomes=[outcome(2019, -1.5, True, -0.3)], dry_threshold=-0.5)
    assert "karşılaştırma yapılamıyor" in test.summary()


def test_summary_lists_every_year():
    outcomes = [outcome(y, -1.0 if y % 2 else 0.5, y % 2 == 1, -0.2) for y in range(2017, 2026)]
    summary = OperationalTest(outcomes=outcomes, dry_threshold=-0.5).summary()
    for year in range(2017, 2026):
        assert str(year) in summary
