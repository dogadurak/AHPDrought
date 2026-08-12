"""AHP çekirdeğinin birim testleri.

Bu modülün kesin, analitik olarak bilinen sonuçları vardır — projenin en iyi
test edilebilen parçası budur ve CI'ın asıl bekçisi burasıdır.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.ahp import (
    DEFAULT_RANDOM_INDEX,
    AHPResult,
    InconsistentMatrixError,
    consistency_ratio,
    geometric_mean_weights,
    perturb_weights,
    principal_eigenvector,
    sensitivity_weight_sets,
    solve_ahp,
    solve_from_config,
    validate_matrix,
)
from src.config import load_config


def consistent_matrix_from(weights: np.ndarray) -> np.ndarray:
    """Verilen ağırlık vektöründen mükemmel tutarlı matris üretir: a_ij = w_i / w_j."""
    w = np.asarray(weights, dtype=float)
    return w[:, None] / w[None, :]


# --- Doğrulama ---------------------------------------------------------------


def test_validate_accepts_reciprocal_matrix():
    m = np.array([[1.0, 3.0], [1 / 3, 1.0]])
    assert validate_matrix(m).shape == (2, 2)


def test_validate_rejects_non_square():
    with pytest.raises(ValueError, match="kare"):
        validate_matrix(np.ones((2, 3)))


def test_validate_rejects_non_reciprocal():
    m = np.array([[1.0, 3.0], [3.0, 1.0]])  # a_ji 1/3 olmalıydı
    with pytest.raises(ValueError, match="Karşılıklılık"):
        validate_matrix(m)


def test_validate_rejects_non_positive():
    m = np.array([[1.0, 0.0], [0.0, 1.0]])
    with pytest.raises(ValueError, match="pozitif"):
        validate_matrix(m)


def test_validate_rejects_bad_diagonal():
    m = np.array([[2.0, 1.0], [1.0, 2.0]])
    with pytest.raises(ValueError, match="Köşegen"):
        validate_matrix(m)


# --- Özvektör ve tutarlılık --------------------------------------------------


@pytest.mark.parametrize(
    "weights",
    [
        np.array([0.5, 0.3, 0.2]),
        np.array([0.4, 0.3, 0.2, 0.1]),
        np.array([0.25, 0.2, 0.18, 0.15, 0.12, 0.07, 0.03]),
    ],
)
def test_perfectly_consistent_matrix_recovers_weights(weights):
    """a_ij = w_i/w_j ise özvektör tam olarak w'yu, lambda_max tam olarak n'i verir."""
    m = consistent_matrix_from(weights)
    n = len(weights)

    computed, lambda_max = principal_eigenvector(m)

    np.testing.assert_allclose(computed, weights, atol=1e-10)
    assert lambda_max == pytest.approx(n, abs=1e-10)


def test_perfectly_consistent_matrix_has_zero_cr():
    m = consistent_matrix_from(np.array([0.5, 0.3, 0.2]))
    result = solve_ahp(m, ["a", "b", "c"])
    assert result.consistency_ratio == pytest.approx(0.0, abs=1e-10)
    assert result.consistency_index == pytest.approx(0.0, abs=1e-10)


def test_geometric_mean_agrees_with_eigenvector_when_consistent():
    """Tutarlı matriste iki yöntem birebir aynı sonucu vermek zorundadır."""
    weights = np.array([0.45, 0.25, 0.20, 0.10])
    m = consistent_matrix_from(weights)
    np.testing.assert_allclose(geometric_mean_weights(m), principal_eigenvector(m)[0], atol=1e-10)


def test_weights_always_sum_to_one():
    rng = np.random.default_rng(42)
    upper = rng.integers(1, 10, size=(5, 5)).astype(float)
    m = np.triu(upper, 1)
    m = m + np.tril(1 / (upper.T + 1e-12), -1)
    np.fill_diagonal(m, 1.0)
    # Karşılıklılığı zorla
    for i in range(5):
        for j in range(i + 1, 5):
            m[j, i] = 1.0 / m[i, j]

    weights, _ = principal_eigenvector(m)
    assert weights.sum() == pytest.approx(1.0)
    assert np.all(weights > 0)


def test_consistency_ratio_known_saaty_example():
    """Saaty'nin klasik 3x3 örneği: CI/RI oranı bilinen aralıkta olmalı."""
    m = np.array(
        [
            [1.0, 1 / 3, 1 / 5],
            [3.0, 1.0, 1 / 3],
            [5.0, 3.0, 1.0],
        ]
    )
    _, lambda_max = principal_eigenvector(m)
    ci, ri, cr = consistency_ratio(lambda_max, 3, DEFAULT_RANDOM_INDEX)

    assert ri == pytest.approx(0.58)
    assert lambda_max > 3.0  # tutarsız matriste lambda_max > n
    assert ci == pytest.approx((lambda_max - 3) / 2)
    assert cr == pytest.approx(ci / ri)
    assert cr < 0.10  # bu matris kabul edilebilir tutarlılıkta


def test_cr_is_zero_for_two_criteria():
    """n <= 2'de tutarsızlık matematiksel olarak imkânsızdır."""
    result = solve_ahp(np.array([[1.0, 7.0], [1 / 7, 1.0]]), ["a", "b"])
    assert result.consistency_ratio == 0.0


# --- Reddetme davranışı ------------------------------------------------------


def test_inconsistent_matrix_is_rejected():
    """Kasıtlı olarak çelişkili matris (a>b, b>c ama c>a) reddedilmeli."""
    m = np.array(
        [
            [1.0, 9.0, 1 / 9],
            [1 / 9, 1.0, 9.0],
            [9.0, 1 / 9, 1.0],
        ]
    )
    with pytest.raises(InconsistentMatrixError, match="CR"):
        solve_ahp(m, ["a", "b", "c"], max_cr=0.10)


def test_inconsistent_matrix_can_be_inspected_without_raising():
    m = np.array([[1.0, 9.0, 1 / 9], [1 / 9, 1.0, 9.0], [9.0, 1 / 9, 1.0]])
    result = solve_ahp(m, ["a", "b", "c"], raise_on_inconsistent=False)
    assert result.consistency_ratio > 0.10


def test_criteria_count_must_match_matrix():
    with pytest.raises(ValueError, match="kriter adı"):
        solve_ahp(np.array([[1.0, 2.0], [0.5, 1.0]]), ["only_one"])


# --- Proje konfigürasyonunun kendisi -----------------------------------------


def test_project_matrix_is_consistent():
    """config.yaml'daki gerçek 7x7 matris CR eşiğini geçmeli.

    Bu test projenin metodolojik kalbidir: matris değiştirildiğinde CI burada
    kırmızıya döner.
    """
    config = load_config()
    result = solve_from_config(config)

    assert result.consistency_ratio <= config["ahp"]["consistency"]["max_cr"]
    assert result.weights.sum() == pytest.approx(1.0)
    assert len(result.criteria) == 7


def test_project_weight_ordering_matches_intent():
    """Yağış ve NDVI baskın, topografik kriterler en düşük ağırlıkta olmalı."""
    result = solve_from_config(load_config())
    w = result.weight_map

    assert w["precipitation"] > w["slope"]
    assert w["ndvi_dry"] > w["aspect"]
    assert w["aspect"] == min(w.values())
    assert w["precipitation"] == max(w.values())


def test_no_criterion_dominates_or_vanishes():
    """Hiçbir kriter anlamsızlaşmamalı; tek kriter haritayı domine etmemeli."""
    result = solve_from_config(load_config())
    assert result.weights.min() > 0.01
    assert result.weights.max() < 0.50


# --- Duyarlılık analizi ------------------------------------------------------


def test_perturb_weights_preserves_sum():
    w = np.array([0.4, 0.3, 0.2, 0.1])
    perturbed = perturb_weights(w, 0, 0.10)
    assert perturbed.sum() == pytest.approx(1.0)
    assert perturbed[0] == pytest.approx(0.44)


def test_perturb_weights_preserves_relative_order_of_others():
    w = np.array([0.4, 0.3, 0.2, 0.1])
    perturbed = perturb_weights(w, 0, -0.10)
    ratio_before = w[1] / w[2]
    ratio_after = perturbed[1] / perturbed[2]
    assert ratio_after == pytest.approx(ratio_before)


def test_sensitivity_produces_two_scenarios_per_criterion():
    result = solve_from_config(load_config())
    sets = sensitivity_weight_sets(result, 0.10)

    assert len(sets) == 2 * len(result.criteria) + 1
    assert "baseline" in sets
    assert "precipitation_plus10" in sets
    assert "aspect_minus10" in sets
    for name, weights in sets.items():
        assert weights.sum() == pytest.approx(1.0), f"{name} toplamı 1 değil"


# --- Raporlama ---------------------------------------------------------------


def test_result_summary_is_renderable():
    result = solve_from_config(load_config())
    text = result.summary()
    assert "CR" in text
    assert "precipitation" in text
    assert isinstance(result, AHPResult)
