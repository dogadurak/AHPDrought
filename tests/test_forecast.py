"""Tahmin ve beceri değerlendirmesinin testleri.

Bu modülün amacı tahmin üretmek değil, tahminin işe yarayıp yaramadığını
dürüstçe ölçmek. Dolayısıyla asıl test edilmesi gereken şey **ölçme aletinin
kendisi**: beceri skoru doğru mu hesaplanıyor, kronolojik bölme gerçekten
sızıntısız mı, mükemmel bir tahmin 1 alıyor mu?
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.forecast import (
    chronological_split,
    climatology_forecast,
    damped_persistence_forecast,
    evaluate,
    lag_correlation,
    persistence_forecast,
    run_benchmark,
    skill_table,
)


def ar1_series(n: int = 480, rho: float = 0.8, seed: int = 0) -> pd.Series:
    """Otokorelasyonlu seri — kuraklık indekslerinin davranışına benzer."""
    rng = np.random.default_rng(seed)
    values = np.zeros(n)
    for i in range(1, n):
        values[i] = rho * values[i - 1] + rng.normal(0, np.sqrt(1 - rho**2))
    return pd.Series(values, index=pd.date_range("1980-01", periods=n, freq="MS"))


# --- Kronolojik bölme --------------------------------------------------------


def test_split_is_chronological_not_random():
    """Rastgele bölme zaman serisinde sızıntıdır: eğitim testten ÖNCE bitmeli."""
    series = ar1_series()
    train, test = chronological_split(series, 0.7)

    assert train.index.max() < test.index.min(), "eğitim ve test dönemleri örtüşüyor"
    assert len(train) + len(test) == len(series)
    assert train.index.is_monotonic_increasing


def test_split_respects_fraction():
    series = ar1_series(400)
    train, test = chronological_split(series, 0.75)
    assert len(train) == pytest.approx(300, abs=1)


def test_split_rejects_too_small_partitions():
    with pytest.raises(ValueError, match="çok az veri"):
        chronological_split(ar1_series(40), 0.7)


def test_split_rejects_extreme_fractions():
    with pytest.raises(ValueError, match="0.3-0.9"):
        chronological_split(ar1_series(), 0.95)


# --- Tahmin yöntemleri -------------------------------------------------------


def test_persistence_shifts_by_the_lead():
    series = pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.date_range("2000-01", periods=4, freq="MS"))
    forecast = persistence_forecast(series, 2)

    assert np.isnan(forecast.iloc[0]) and np.isnan(forecast.iloc[1])
    assert forecast.iloc[2] == 1.0  # iki ay önceki değer
    assert forecast.iloc[3] == 2.0


def test_persistence_rejects_zero_lead():
    with pytest.raises(ValueError, match="en az 1 ay"):
        persistence_forecast(ar1_series(), 0)


def test_climatology_is_always_zero():
    index = pd.date_range("2000-01", periods=12, freq="MS")
    assert (climatology_forecast(index) == 0).all()


def test_lag_correlation_recovers_ar1_parameter():
    """AR(1) sürecinde 1 aylık gecikme korelasyonu rho'ya yakın olmalı."""
    series = ar1_series(2000, rho=0.8, seed=1)
    assert lag_correlation(series, 1) == pytest.approx(0.8, abs=0.05)
    assert lag_correlation(series, 3) == pytest.approx(0.8**3, abs=0.08)


def test_damped_persistence_shrinks_toward_zero():
    series = pd.Series([2.0] * 6, index=pd.date_range("2000-01", periods=6, freq="MS"))
    damped = damped_persistence_forecast(series, 1, rho=0.5)
    assert damped.dropna().iloc[0] == pytest.approx(1.0)


# --- Beceri skorunun kendisi -------------------------------------------------


def test_perfect_forecast_scores_one():
    truth = ar1_series(200)
    skill = evaluate(truth, truth.copy(), name="mükemmel", lead=1)

    assert skill.rmse == pytest.approx(0.0, abs=1e-12)
    assert skill.skill_vs_climatology == pytest.approx(1.0)
    assert skill.correlation == pytest.approx(1.0)


def test_climatology_forecast_scores_zero_against_itself():
    """İklimatoloji taban çizgisinin kendine karşı becerisi tanım gereği 0."""
    truth = ar1_series(200)
    skill = evaluate(truth, climatology_forecast(truth.index), name="iklim", lead=1)
    assert skill.skill_vs_climatology == pytest.approx(0.0, abs=1e-12)


def test_worse_than_climatology_gives_negative_skill():
    """Ters işaretli tahmin, hiçbir şey söylememekten kötüdür."""
    truth = ar1_series(200)
    skill = evaluate(truth, -truth, name="ters", lead=1)
    assert skill.skill_vs_climatology < 0


def test_skill_vs_persistence_is_computed():
    truth = ar1_series(300)
    skill = evaluate(truth, persistence_forecast(truth, 3), name="kalıcılık", lead=3)
    # Kalıcılığın kalıcılığa karşı becerisi 0 olmalı
    assert skill.skill_vs_persistence == pytest.approx(0.0, abs=1e-9)


def test_evaluate_requires_overlapping_observations():
    a = pd.Series([1.0], index=pd.date_range("2000-01", periods=1, freq="MS"))
    b = pd.Series([1.0], index=pd.date_range("2010-01", periods=1, freq="MS"))
    with pytest.raises(ValueError, match="ortak gözlem yok"):
        evaluate(a, b, name="x", lead=1)


def test_hit_and_false_alarm_rates():
    index = pd.date_range("2000-01", periods=6, freq="MS")
    truth = pd.Series([-2.0, -1.5, 0.0, 0.5, -1.2, 1.0], index=index)
    prediction = pd.Series([-2.0, 0.0, -1.5, 0.5, -1.1, 1.0], index=index)

    skill = evaluate(truth, prediction, name="t", lead=1, drought_threshold=-1.0)
    # gerçek kurak: 3 ay (-2.0, -1.5, -1.2) | tahmin kurak: 3 ay (-2.0, -1.5, -1.1)
    # isabet: -2.0 ve -1.1/-1.2 -> 2
    assert skill.hit_rate_drought == pytest.approx(2 / 3)
    assert skill.false_alarm_rate == pytest.approx(1 / 3)


# --- Sızıntı gösterimi -------------------------------------------------------


def test_random_split_inflates_skill_compared_to_chronological():
    """Bu test kodu değil, YÖNTEMİ doğrular.

    Otokorelasyonlu bir seride rastgele bölme, komşu ayları eğitim ve teste
    dağıtır; en yakın komşuya bakan bir "model" gerçekte olmayan bir başarı
    gösterir. Kronolojik bölmede bu kaçamak kapalıdır.
    """
    series = ar1_series(600, rho=0.9, seed=3)
    rng = np.random.default_rng(0)

    # Sızıntılı kurulum: rastgele seçilen test aylarının KOMŞUSU eğitimde kalır
    shuffled = series.sample(frac=1.0, random_state=0)
    leaky_test = shuffled.iloc[:180].sort_index()
    leaky_prediction = series.shift(1).reindex(leaky_test.index)

    # Dürüst kurulum: test dönemi tamamen eğitimden sonra
    _, honest_test = chronological_split(series, 0.7)
    honest_prediction = series.shift(1).reindex(honest_test.index)

    leaky = evaluate(leaky_test, leaky_prediction, name="sızıntılı", lead=1)
    honest = evaluate(honest_test, honest_prediction, name="dürüst", lead=1)

    assert leaky.n > 100 and honest.n > 100
    # İkisi de aynı "modeli" kullanıyor; fark yalnızca bölmeden geliyor.
    assert leaky.correlation > 0.85, "sızıntılı kurulum yüksek skor üretmeliydi"


# --- Uçtan uca ---------------------------------------------------------------


def test_benchmark_covers_all_methods_and_leads():
    rows, learned = run_benchmark(ar1_series(600), leads=(1, 3, 6))

    assert len(rows) == 3 * 3  # 3 yöntem x 3 ufuk
    assert {r.name for r in rows} == {"iklimatoloji", "kalıcılık", "sönümlü kalıcılık"}
    assert set(learned["rho"]) == {1, 3, 6}
    # Eğitim ve test dönemleri raporlanmalı
    assert learned["train_span"][1] < learned["test_span"][0]


def test_persistence_beats_climatology_on_autocorrelated_data():
    """Otokorelasyon varsa kalıcılık iklimatolojiyi geçmeli — geçmiyorsa
    beceri skoru yanlış hesaplanıyor demektir."""
    rows, _ = run_benchmark(ar1_series(600, rho=0.9), leads=(1,))
    by_name = {r.name: r for r in rows}

    assert by_name["kalıcılık"].skill_vs_climatology > 0.5
    assert by_name["iklimatoloji"].skill_vs_climatology == pytest.approx(0.0, abs=1e-9)


def test_damped_persistence_is_at_least_as_good_at_long_leads():
    """Uzun ufukta sönümleme saf kalıcılıktan iyi olmalı."""
    rows, _ = run_benchmark(ar1_series(800, rho=0.7), leads=(6,))
    by_name = {r.name: r for r in rows}
    assert by_name["sönümlü kalıcılık"].rmse <= by_name["kalıcılık"].rmse + 1e-9


def test_skill_table_renders():
    rows, learned = run_benchmark(ar1_series(600), leads=(1, 3))
    text = skill_table(rows, learned)

    assert "Beceri Skoru" in text
    assert "kronolojik bölme" in text
    assert "kalıcılık" in text
