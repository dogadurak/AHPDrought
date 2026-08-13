"""Ağırlıklı çakıştırma ve sınıflandırma testleri (Adım 4-5)."""

from __future__ import annotations

import numpy as np
import pytest

from src.ahp import solve_from_config
from src.classify import apply_breaks, class_summary, compute_breaks
from src.config import load_config
from src.criteria.normalize import NormalizationError, normalize_criterion
from src.overlay import CriteriaStack, weighted_overlay


@pytest.fixture
def config():
    return load_config()


def make_stack(*layers: np.ndarray) -> CriteriaStack:
    data = np.stack([np.asarray(layer, dtype="float32") for layer in layers])
    return CriteriaStack(
        names=tuple(f"c{i}" for i in range(len(layers))),
        data=data,
        valid_mask=~np.isnan(data).any(axis=0),
    )


# --- Normalizasyon -----------------------------------------------------------


def test_minmax_percentile_maps_to_unit_range():
    data = np.linspace(10, 20, 101).reshape(101, 1)
    spec = {"normalization": "minmax_percentile", "higher_is_riskier": True, "percentile_clip": [0, 100]}
    out = normalize_criterion(data, spec)
    assert out.min() == pytest.approx(0.0)
    assert out.max() == pytest.approx(1.0)


def test_low_is_riskier_inverts_the_scale():
    """Yağış ve NDVI için: düşük ham değer YÜKSEK risk skoru vermeli."""
    data = np.array([[10.0, 20.0]])
    spec = {"normalization": "minmax_percentile", "higher_is_riskier": False, "percentile_clip": [0, 100]}
    out = normalize_criterion(data, spec)
    assert out[0, 0] == pytest.approx(1.0)   # az yağış -> yüksek risk
    assert out[0, 1] == pytest.approx(0.0)


def test_percentile_clip_resists_a_single_outlier():
    """Tek bir aykırı piksel tüm ölçeği ezmemeli.

    Ham min-max kullanılsaydı 0-10 aralığındaki gerçek veri, 10000'lik tek bir
    artefakt yüzünden 0-0.001 bandına sıkışır ve kriter ayrım üretemezdi.
    """
    data = np.concatenate([np.linspace(0.0, 10.0, 999), [10_000.0]]).reshape(-1, 1)
    spec = {"normalization": "minmax_percentile", "higher_is_riskier": True, "percentile_clip": [2, 98]}
    out = normalize_criterion(data, spec)

    real_data = out[:999]
    assert real_data.min() == pytest.approx(0.0, abs=1e-6)
    assert real_data.max() == pytest.approx(1.0, abs=1e-6), "gerçek veri tüm ölçeği kullanmalı"
    assert out[999] == pytest.approx(1.0)  # aykırı değer kırpılıp tavana oturur

    naive = (data - data.min()) / (data.max() - data.min())
    assert naive[:999].max() < 0.002, "karşılaştırma: ham min-max ölçeği ezerdi"


def test_capped_normalization_saturates():
    data = np.array([[0.0, 7500.0, 15000.0, 30000.0]])
    spec = {"normalization": "minmax_capped", "higher_is_riskier": True, "cap_value_m": 15000}
    out = normalize_criterion(data, spec)
    np.testing.assert_allclose(out, [[0.0, 0.5, 1.0, 1.0]], atol=1e-6)


def test_normalization_preserves_nan():
    data = np.array([[1.0, np.nan, 3.0]])
    spec = {"normalization": "minmax_percentile", "higher_is_riskier": True, "percentile_clip": [0, 100]}
    out = normalize_criterion(data, spec)
    assert np.isnan(out[0, 1])
    assert np.isfinite(out[0, 0]) and np.isfinite(out[0, 2])


def test_constant_layer_is_rejected():
    """Sabit bir katman hiçbir ayrım üretmez; sessizce 0 döndürmek yerine hata."""
    spec = {"normalization": "minmax_percentile", "higher_is_riskier": True, "percentile_clip": [2, 98]}
    with pytest.raises(NormalizationError, match="sabit görünüyor"):
        normalize_criterion(np.full((10, 10), 42.0), spec)


def test_passthrough_rejects_out_of_range():
    spec = {"normalization": "none", "higher_is_riskier": True}
    with pytest.raises(NormalizationError, match="0-1 aralığı"):
        normalize_criterion(np.array([[0.5, 1.7]]), spec)


def test_unknown_method_is_rejected():
    with pytest.raises(NormalizationError, match="bilinmeyen normalizasyon"):
        normalize_criterion(np.zeros((2, 2)), {"normalization": "sihir", "higher_is_riskier": True})


# --- Ağırlıklı çakıştırma ----------------------------------------------------


def test_overlay_is_a_weighted_mean():
    stack = make_stack(np.full((2, 2), 1.0), np.full((2, 2), 0.0))
    out = weighted_overlay(stack, np.array([0.75, 0.25]))
    np.testing.assert_allclose(out, 0.75)


def test_overlay_output_stays_in_unit_range():
    rng = np.random.default_rng(7)
    stack = make_stack(*[rng.random((20, 20)) for _ in range(7)])
    weights = solve_from_config(load_config()).weights

    out = weighted_overlay(stack, weights)
    assert out.min() >= 0.0
    assert out.max() <= 1.0


def test_missing_criterion_masks_the_pixel():
    """Eksik kriteri sıfır saymak pikseli yapay olarak 'düşük riskli' gösterirdi."""
    a = np.array([[1.0, 1.0]])
    b = np.array([[1.0, np.nan]])
    out = weighted_overlay(make_stack(a, b), np.array([0.5, 0.5]))

    assert out[0, 0] == pytest.approx(1.0)
    assert np.isnan(out[0, 1]), "eksik kriterli piksel maskelenmeliydi"


def test_overlay_rejects_weights_that_do_not_sum_to_one():
    stack = make_stack(np.zeros((2, 2)), np.zeros((2, 2)))
    with pytest.raises(ValueError, match="toplamı 1"):
        weighted_overlay(stack, np.array([0.5, 0.4]))


def test_overlay_rejects_wrong_weight_count():
    stack = make_stack(np.zeros((2, 2)), np.zeros((2, 2)))
    with pytest.raises(ValueError, match="ağırlık verildi"):
        weighted_overlay(stack, np.array([1.0]))


def test_overlay_rejects_negative_weights():
    stack = make_stack(np.zeros((2, 2)), np.zeros((2, 2)))
    with pytest.raises(ValueError, match="negatif"):
        weighted_overlay(stack, np.array([1.5, -0.5]))


# --- Sınıflandırma -----------------------------------------------------------


def test_equal_interval_breaks_are_evenly_spaced():
    breaks = compute_breaks(np.linspace(0, 1, 1000), method="equal_interval", n_classes=5)
    np.testing.assert_allclose(np.diff(breaks), 0.2, atol=1e-6)


def test_quantile_breaks_split_population_evenly():
    values = np.random.default_rng(0).random(10_000)
    breaks = compute_breaks(values, method="quantile", n_classes=5)
    classes = apply_breaks(values, breaks, 5)
    shares = [np.mean(classes == c) for c in range(1, 6)]
    assert max(shares) - min(shares) < 0.02


def test_jenks_breaks_are_monotonic_and_cover_the_data():
    values = np.random.default_rng(1).beta(2, 5, 50_000)
    breaks = compute_breaks(values, method="jenks", n_classes=5, sample_size=20_000)

    assert breaks.size == 5
    assert np.all(np.diff(breaks) > 0), "sınıf sınırları artan olmalı"
    assert breaks[-1] >= values.max(), "son sınır tüm veriyi kapsamalı"


def test_jenks_is_reproducible():
    values = np.random.default_rng(2).beta(2, 5, 50_000)
    a = compute_breaks(values, method="jenks", n_classes=5, sample_size=10_000)
    b = compute_breaks(values, method="jenks", n_classes=5, sample_size=10_000)
    np.testing.assert_allclose(a, b)


def test_every_valid_pixel_gets_a_class():
    values = np.random.default_rng(3).random((100, 100))
    breaks = compute_breaks(values, method="jenks", n_classes=5, sample_size=5000)
    classes = apply_breaks(values, breaks, 5)

    assert classes.min() >= 1
    assert classes.max() <= 5
    assert not (classes == 0).any(), "geçerli piksel sınıfsız kalmamalı"


def test_invalid_pixels_get_class_zero():
    values = np.array([[0.1, np.nan, 0.9]])
    breaks = np.array([0.2, 0.4, 0.6, 0.8, 1.0])
    classes = apply_breaks(values, breaks, 5)

    assert classes[0, 1] == 0
    assert classes[0, 0] == 1
    assert classes[0, 2] == 5


def test_break_count_must_match_class_count():
    with pytest.raises(ValueError, match="sınır gerekir"):
        apply_breaks(np.zeros((2, 2)), np.array([0.5, 1.0]), 5)


def test_classification_rejects_too_few_distinct_values():
    with pytest.raises(ValueError, match="farklı değer"):
        compute_breaks(np.array([0.1, 0.2, 0.1, 0.2]), method="jenks", n_classes=5)


def test_class_summary_renders(config):
    values = np.random.default_rng(4).random((50, 50))
    breaks = compute_breaks(values, method="jenks", n_classes=5, sample_size=2000)
    text = class_summary(config, apply_breaks(values, breaks, 5), breaks)

    assert "Çok yüksek" in text
    assert "TOPLAM" in text
