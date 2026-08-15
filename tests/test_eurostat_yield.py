"""Eurostat verim modülünün testleri.

Bu modülün asıl işlevi veri getirmek değil, **getirdiği verinin kullanılamaz
olduğunu yakalamak**. Denetimler olmasaydı beş uydurma yıl (üretim = alan
raporlanmış) ve iki fiziksel olarak imkânsız pamuk verimi analize girerdi.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.fetch.eurostat_yield import CROPS, _yield_with_quality_checks, yield_anomaly


def test_identical_production_and_area_is_rejected():
    """Regresyon: TR33 tahılında 2000-2004 için ikisi de aynı sayı raporlanmış.

    Bölünce tam 1.00 t/ha çıkıyordu — gerçek bir verim değil, veri giriş hatası.
    """
    production = pd.DataFrame({"tahil": [2250.9, 1921.1, 2079.0]}, index=[2000, 2001, 2011])
    area = pd.DataFrame({"tahil": [2250.9, 1921.1, 819.0]}, index=[2000, 2001, 2011])

    result, dropped = _yield_with_quality_checks(production, area)

    # Elenen yıllar ya NaN kalır ya da (tüm sütunları boşaldığı için) düşer
    for year in (2000, 2001):
        assert year not in result.index or pd.isna(result.loc[year, "tahil"])
    assert result.loc[2011, "tahil"] == pytest.approx(2.54, abs=0.01)
    assert any("birebir aynı" in reason for reason in dropped)


def test_physically_impossible_yields_are_rejected():
    """Pamuk lifinde 5.33 t/ha görüldü; dünya rekoru bunun yarısı kadar."""
    production = pd.DataFrame({"pamuk_lifi": [80.0, 40.0]}, index=[2016, 2018])
    area = pd.DataFrame({"pamuk_lifi": [15.0, 17.4]}, index=[2016, 2018])

    result, dropped = _yield_with_quality_checks(production, area)

    assert 2016 not in result.index or pd.isna(result.loc[2016, "pamuk_lifi"])
    assert result.loc[2018, "pamuk_lifi"] == pytest.approx(2.30, abs=0.01)
    assert any("fiziksel aralık" in reason for reason in dropped)


def test_plausible_values_pass_through():
    production = pd.DataFrame({"tahil": [2100.0]}, index=[2020])
    area = pd.DataFrame({"tahil": [750.0]}, index=[2020])

    result, dropped = _yield_with_quality_checks(production, area)
    assert result.loc[2020, "tahil"] == pytest.approx(2.8)
    assert not dropped


def test_zero_area_does_not_produce_infinity():
    production = pd.DataFrame({"tahil": [2100.0]}, index=[2020])
    area = pd.DataFrame({"tahil": [0.0]}, index=[2020])

    result, _ = _yield_with_quality_checks(production, area)
    assert result.empty or pd.isna(result.loc[2020, "tahil"])


def test_detrending_removes_technological_trend():
    """Verim ıslah ve sulama yatırımıyla on yıllar boyunca artar.

    Eğilim çıkarılmazsa erken yıllar 'kuraklık', geç yıllar 'bolluk' diye
    okunur — teknolojik gelişme iklim sinyaliyle karışır.
    """
    years = list(range(2000, 2020))
    rising = pd.DataFrame({"tahil": [2.0 + 0.05 * (y - 2000) for y in years]}, index=years)

    with_trend = yield_anomaly(rising, detrend=False)["tahil"]
    detrended = yield_anomaly(rising, detrend=True)

    # Eğilim çıkarılmazsa ilk yıllar güçlü negatif, son yıllar güçlü pozitif
    assert with_trend.iloc[0] < -1.5 and with_trend.iloc[-1] > 1.5
    # Tam doğrusal seride eğilim çıkınca artık kalmaz; z-skoru tanımsızdır ve
    # sıfıra bölme gürültüsü üretmek yerine sütun düşürülmelidir.
    assert "tahil" not in detrended.columns


def test_detrending_keeps_real_variability():
    """Eğilim üstünde gerçek dalgalanma varsa anomali üretilmeli."""
    import numpy as np

    years = list(range(2000, 2020))
    rng = np.random.default_rng(0)
    values = [2.0 + 0.05 * (y - 2000) + rng.normal(0, 0.3) for y in years]
    frame = pd.DataFrame({"tahil": values}, index=years)

    anomaly = yield_anomaly(frame, detrend=True)["tahil"]
    assert abs(anomaly.mean()) < 0.2
    assert 0.8 < anomaly.std() < 1.2


def test_short_series_is_skipped():
    frame = pd.DataFrame({"tahil": [2.0, 2.1, 2.2]}, index=[2020, 2021, 2022])
    assert yield_anomaly(frame).empty


def test_target_crops_cover_the_basin():
    """Gediz'in ana ürünleri istenmiş olmalı (verilerinin gelip gelmemesi ayrı)."""
    assert set(CROPS.values()) >= {"uzum", "zeytin", "pamuk_lifi"}
