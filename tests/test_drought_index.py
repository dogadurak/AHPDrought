"""SPI hesabının testleri.

SPI'ın tanımı gereği doğrulanabilir özellikleri var: uzun dönemde ortalaması 0,
standart sapması 1 olmalı ve mevsimsellik TAŞIMAMALI. Son madde en kritik olanı:
takvim ayı bazında uyarlama yapılmazsa ağustosun kuru olması "kuraklık" diye
okunur ve indeks anlamını yitirir.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.drought_index import (
    MIN_CALIBRATION_YEARS,
    accumulate,
    classify_spi,
    drought_events,
    spi,
)


def monthly_index(years: int, start: str = "1960-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=years * 12, freq="MS")


def mediterranean_precipitation(years: int = 60, seed: int = 0) -> pd.Series:
    """Akdeniz rejimi: yazlar tamamen kuru, kışlar yağışlı.

    Gerçek Gediz iklimatolojisine yakın aylık ortalamalar kullanılır — testin
    anlamlı olması için mevsimsellik güçlü olmalı.
    """
    climatology = [110, 85, 70, 45, 25, 10, 3, 3, 15, 45, 80, 120]
    rng = np.random.default_rng(seed)
    index = monthly_index(years)
    values = []
    for timestamp in index:
        mean = climatology[timestamp.month - 1]
        # Gama benzeri çarpımsal değişkenlik; yaz aylarında sık sık tam sıfır
        value = rng.gamma(shape=2.0, scale=mean / 2.0) if mean > 5 else rng.gamma(1.0, mean)
        if mean <= 5 and rng.random() < 0.5:
            value = 0.0
        values.append(value)
    return pd.Series(values, index=index)


# --- Biriktirme --------------------------------------------------------------


def test_accumulate_sums_the_window():
    series = pd.Series(range(12), index=monthly_index(1), dtype=float)
    rolled = accumulate(series, 3)

    assert np.isnan(rolled.iloc[0]) and np.isnan(rolled.iloc[1])
    assert rolled.iloc[2] == pytest.approx(0 + 1 + 2)
    assert rolled.iloc[11] == pytest.approx(9 + 10 + 11)


def test_accumulate_rejects_bad_input():
    series = pd.Series(range(12), index=monthly_index(1), dtype=float)
    with pytest.raises(ValueError, match="en az 1 ay"):
        accumulate(series, 0)
    with pytest.raises(TypeError, match="DatetimeIndex"):
        accumulate(pd.Series([1.0, 2.0]), 3)


# --- SPI'ın tanım gereği taşıması gereken özellikler --------------------------


@pytest.mark.parametrize("scale", [1, 3, 6, 12])
def test_spi_is_standard_normal(scale):
    """Uzun dönemde ortalama ~0, standart sapma ~1 olmalı."""
    result = spi(mediterranean_precipitation(60), scale=scale)
    values = result.values.dropna()

    assert abs(values.mean()) < 0.15, f"SPI-{scale} ortalaması {values.mean():.3f}, ~0 olmalıydı"
    assert 0.8 < values.std() < 1.2, f"SPI-{scale} std {values.std():.3f}, ~1 olmalıydı"


def test_spi_removes_seasonality():
    """EN KRİTİK TEST: kuru yaz, kuraklık olarak okunmamalı.

    Takvim ayı bazında uyarlama yapılmazsa temmuz-ağustos SPI'ı sistematik
    olarak negatife kayar ve indeks mevsimi kuraklık sanır.
    """
    result = spi(mediterranean_precipitation(60), scale=3)
    values = result.values.dropna()
    monthly_means = values.groupby(values.index.month).mean()

    assert monthly_means.abs().max() < 0.35, (
        f"aylık SPI ortalamaları sıfırdan sapıyor — mevsimsellik temizlenmemiş:\n"
        f"{monthly_means.round(3).to_dict()}"
    )
    # Yaz ayları özellikle kontrol edilir (tam kuru geçen aylar burada)
    for month in (7, 8):
        assert abs(monthly_means[month]) < 0.4, (
            f"{month}. ay ortalaması {monthly_means[month]:+.3f} — kuru mevsim "
            "kuraklık sanılıyor olabilir"
        )


def test_spi_is_monotone_within_a_calendar_month():
    """Aynı ay içinde daha çok yağış, daha yüksek SPI vermeli."""
    precipitation = mediterranean_precipitation(60)
    result = spi(precipitation, scale=1)

    january = result.values[result.values.index.month == 1].dropna()
    january_rain = precipitation[precipitation.index.month == 1].reindex(january.index)

    from scipy.stats import rankdata

    corr = np.corrcoef(rankdata(january_rain), rankdata(january))[0, 1]
    assert corr > 0.99, f"ay içi sıralama korunmuyor (ρ={corr:.4f})"


def test_dry_year_produces_negative_spi():
    """Kasten kurak geçirilen bir yıl belirgin negatif SPI vermeli."""
    precipitation = mediterranean_precipitation(60)
    dry_year = precipitation.index.year == 2000
    precipitation[dry_year] = precipitation[dry_year] * 0.15

    result = spi(precipitation, scale=12)
    during = result.values[result.values.index.year == 2000].dropna()
    assert during.min() < -1.0, f"kurak yılda en düşük SPI {during.min():.2f}, < -1 olmalıydı"


def test_zero_precipitation_does_not_produce_infinity():
    """Thom (1958) düzeltmesi olmadan sıfırlar -sonsuza gider."""
    precipitation = mediterranean_precipitation(60)
    precipitation[precipitation.index.month.isin([7, 8])] = 0.0

    result = spi(precipitation, scale=1)
    values = result.values.dropna()
    assert np.isfinite(values).all(), "SPI'da sonsuz/NaN değer var"
    assert values.min() > -5, f"aşırı negatif değer: {values.min():.2f}"


def test_zero_fraction_is_recorded():
    precipitation = mediterranean_precipitation(60)
    precipitation[precipitation.index.month == 8] = 0.0

    result = spi(precipitation, scale=1)
    assert result.zero_fraction[8] == pytest.approx(1.0)


# --- Kalibrasyon -------------------------------------------------------------


def test_short_calibration_is_rejected():
    """WMO en az 30 yıl önerir; kısa seri sessizce kabul edilmemeli."""
    with pytest.raises(ValueError, match="en az .* yıl"):
        spi(mediterranean_precipitation(10), scale=3)


def test_calibration_period_is_respected():
    precipitation = mediterranean_precipitation(60)
    result = spi(precipitation, scale=3, calibration=("1960-01", "1999-12"))

    assert result.calibration == ("1960-01", "1999-12")
    # Kalibrasyon dışındaki dönem için de SPI üretilmeli
    assert result.values[result.values.index.year >= 2000].notna().any()


def test_min_calibration_years_matches_wmo():
    assert MIN_CALIBRATION_YEARS == 30


# --- Sınıflandırma ve olaylar ------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (-2.5, "Olağanüstü kurak"),
        (-1.7, "Şiddetli kurak"),
        (-1.2, "Orta kurak"),
        (-0.7, "Hafif kurak"),
        (0.0, "Normale yakın"),
        (1.2, "Orta nemli"),
        (2.5, "Olağanüstü nemli"),
    ],
)
def test_spi_classification(value, expected):
    assert classify_spi(value) == expected


def test_classification_handles_missing():
    assert classify_spi(np.nan) == "veri yok"


def test_drought_events_group_consecutive_months():
    index = monthly_index(2)
    values = np.zeros(24)
    values[3:9] = -1.5      # 6 aylık olay
    values[15:17] = -1.2    # 2 aylık olay
    series = pd.Series(values, index=index)

    events = drought_events(series, threshold=-1.0)
    assert len(events) == 2
    assert set(events["süre_ay"]) == {6, 2}
    # En şiddetli olay (kümülatif açığı en büyük) ilk sırada
    assert events.iloc[0]["süre_ay"] == 6


def test_no_drought_returns_empty():
    series = pd.Series(np.zeros(24), index=monthly_index(2))
    assert drought_events(series).empty
