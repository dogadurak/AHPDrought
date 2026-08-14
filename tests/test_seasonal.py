"""Mevsimsel öngörü modülünün testleri.

En kritik olanlar sızıntı testleri: öngörücü ile hedef dönem kesişirse ya da
katsayılar test döneminden öğrenilirse, beceri skoru gerçekte olmayan bir
başarı gösterir ve bunu fark etmek çıplak gözle imkânsızdır.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.seasonal import (
    build_dataset,
    evaluate_seasonal,
    seasonal_mean,
    seasonal_skill_table,
)


def synthetic_climate(years: int = 60, seed: int = 0, link: float = 0.8) -> pd.DataFrame:
    """Akdeniz rejimi + kış suyu ile yaz toprak nemi arasında bilinen bir bağ.

    `link` gücünde gerçek bir fiziksel bağ kurulur; testler modülün bu bağı
    bulup bulamadığını sınar.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range("1960-01", periods=years * 12, freq="MS")
    climatology = [110, 85, 70, 45, 25, 10, 3, 3, 15, 45, 80, 120]

    ppt, soil, pdsi = [], [], []
    winter_store = 100.0
    for timestamp in index:
        mean = climatology[timestamp.month - 1]
        rain = max(0.0, rng.gamma(2.0, mean / 2.0))
        ppt.append(rain)

        if timestamp.month in (11, 12, 1, 2, 3, 4):
            winter_store = winter_store * 0.7 + rain * 0.6
        # Yaz nemi kış deposuna bağlı, üstüne gürültü
        seasonal_drain = 0.85 if timestamp.month in (5, 6, 7, 8, 9) else 1.0
        winter_store *= seasonal_drain
        soil.append(link * winter_store + (1 - link) * rng.normal(60, 20))
        pdsi.append(rng.normal(0, 1))

    return pd.DataFrame({"ppt": ppt, "soil": soil, "pdsi": pdsi}, index=index)


# --- Sızıntı koruması --------------------------------------------------------


def test_overlapping_predictor_and_target_months_are_rejected():
    """Öngörücü ile hedef ayları kesişirse hedeften bilgi sızar."""
    frame = synthetic_climate(40)
    with pytest.raises(ValueError, match="kesişiyor"):
        build_dataset(frame, predictor_months=(6, 7), target_months=(7, 8, 9))


def test_predictor_must_end_before_target_starts():
    """Öngörücü hedeften SONRA bitiyorsa tahmin ileriye dönük değildir."""
    frame = synthetic_climate(40)
    with pytest.raises(ValueError, match="önce"):
        build_dataset(frame, predictor_months=(10, 11), target_months=(7, 8, 9))


def test_default_configuration_is_forward_looking():
    frame = synthetic_climate(40)
    dataset = build_dataset(frame, predictor_months=(3, 4), target_months=(7, 8, 9))
    assert "3, 4" in dataset.predictor_season or "(3, 4)" in dataset.predictor_season
    assert len(dataset.target) > 30


def test_fit_uses_only_training_years():
    """Katsayılar test döneminden öğrenilirse gelecekten bilgi sızar.

    Aynı veriyle iki farklı eğitim oranı, farklı katsayılar üretmeli — aksi
    halde uyarlama test dönemini de görüyor demektir.
    """
    dataset = build_dataset(synthetic_climate(60), target_column="soil")
    _, learned_70 = evaluate_seasonal(dataset, train_fraction=0.7)
    _, learned_50 = evaluate_seasonal(dataset, train_fraction=0.5)

    name = next(iter(learned_70["fits"]))
    assert learned_70["fits"][name] != learned_50["fits"][name]
    assert learned_70["train_span"][1] > learned_50["train_span"][1]


def test_train_and_test_periods_do_not_overlap():
    dataset = build_dataset(synthetic_climate(60), target_column="soil")
    _, learned = evaluate_seasonal(dataset)
    assert learned["train_span"][1] < learned["test_span"][0]


# --- Mevsimsel özetleme ------------------------------------------------------


def test_seasonal_mean_groups_by_year():
    index = pd.date_range("2000-01", periods=36, freq="MS")
    series = pd.Series(range(36), index=index, dtype=float)
    summer = seasonal_mean(series, (7, 8, 9))

    assert list(summer.index) == [2000, 2001, 2002]
    assert summer.loc[2000] == pytest.approx(np.mean([6, 7, 8]))


def test_water_year_shifts_november_december_forward():
    """Kasım-aralık yağışı BİR SONRAKİ yazı besler; aynı yıla sayılmamalı."""
    dataset = build_dataset(synthetic_climate(40))
    assert "yas_mevsim_yagisi" in dataset.predictors.columns
    # Su yılı kaydırması yapıldığı için ilk yıl eksik kalır
    assert dataset.predictors["yas_mevsim_yagisi"].index.min() >= dataset.target.index.min()


# --- Beceri değerlendirmesi --------------------------------------------------


def test_real_physical_link_is_detected():
    """Sentetik veride kurulan gerçek bağ, becerinin pozitif çıkmasını sağlamalı."""
    dataset = build_dataset(synthetic_climate(70, link=0.9), target_column="soil")
    rows, _ = evaluate_seasonal(dataset)

    predictors = [r for r in rows if "iklimatoloji" not in r.name and "kalıcılık" not in r.name]
    assert predictors, "hiç öngörücü değerlendirilmemiş"
    assert max(r.skill_vs_climatology for r in predictors) > 0.2, (
        "kurulan gerçek fiziksel bağ bulunamadı"
    )


def test_no_link_gives_no_skill():
    """Bağ yoksa beceri de olmamalı — modül olmayan sinyali uydurmamalı."""
    rng = np.random.default_rng(3)
    index = pd.date_range("1960-01", periods=70 * 12, freq="MS")
    frame = pd.DataFrame(
        {
            "ppt": rng.gamma(2.0, 30.0, len(index)),
            "soil": rng.normal(60, 20, len(index)),  # yağıştan tamamen bağımsız
        },
        index=index,
    )
    dataset = build_dataset(frame, target_column="soil")
    rows, _ = evaluate_seasonal(dataset)

    predictors = [r for r in rows if "iklimatoloji" not in r.name and "kalıcılık" not in r.name]
    assert max(r.skill_vs_climatology for r in predictors) < 0.15, (
        "olmayan bir bağ için beceri raporlanıyor"
    )


def test_climatology_baseline_has_zero_skill_against_itself():
    dataset = build_dataset(synthetic_climate(60), target_column="soil")
    rows, _ = evaluate_seasonal(dataset)
    climatology = next(r for r in rows if "iklimatoloji" in r.name)
    assert climatology.skill_vs_climatology == pytest.approx(0.0, abs=1e-9)


def test_short_series_is_rejected():
    with pytest.raises(ValueError, match="çok az yıl"):
        evaluate_seasonal(build_dataset(synthetic_climate(20), target_column="soil"))


def test_skill_table_renders_both_baselines():
    dataset = build_dataset(synthetic_climate(60), target_column="soil")
    rows, learned = evaluate_seasonal(dataset)
    text = seasonal_skill_table(rows, learned, dataset)

    assert "BS-iklim" in text and "BS-kalici" in text
    assert "kronolojik" in text
    assert "HEM iklimatolojiyi HEM kaliciligi" in text


def test_missing_target_column_raises():
    with pytest.raises(KeyError, match="yok"):
        build_dataset(synthetic_climate(40), target_column="olmayan")
