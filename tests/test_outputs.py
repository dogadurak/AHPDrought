"""Üretilmiş nihai çıktıların doğrulanması (Adım 4-7).

Bu testler ürün varsa çalışır, yoksa atlanır — CI'da ham veri olmadığından
sessizce geçer, geliştirme makinesinde ise sonuçların fiziksel makullüğünü
denetler.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.classify import classify_risk
from src.config import load_config
from src.fetch.common import interim_path, resolve
from src.grid import build_grid, read_grid_aligned
from src.overlay import load_criteria, weighted_overlay


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def grid(config):
    return build_grid(config)


@pytest.fixture(scope="module")
def stack(config, grid):
    missing = [n for n in config.criteria_order if not config.criterion_path(n).exists()]
    if missing:
        pytest.skip(f"kriterler eksik: {missing}")
    return load_criteria(config, grid)


@pytest.fixture(scope="module")
def risk(config, stack):
    from src.ahp import solve_from_config

    return weighted_overlay(stack, solve_from_config(config).weights)


# --- Kriter katmanları -------------------------------------------------------


def test_every_criterion_is_in_unit_range(config, stack):
    for name, layer in zip(stack.names, stack.data):
        finite = layer[np.isfinite(layer)]
        assert finite.min() >= -1e-6, f"{name}: 0'ın altında değer var ({finite.min()})"
        assert finite.max() <= 1 + 1e-6, f"{name}: 1'in üstünde değer var ({finite.max()})"


def test_criteria_are_not_constant(config, stack):
    """Sabit bir kriter hiçbir ayrım üretmez — sessizce boşa ağırlık harcar."""
    for name, layer in zip(stack.names, stack.data):
        finite = layer[np.isfinite(layer)]
        assert finite.std() > 0.01, f"{name}: neredeyse sabit (std={finite.std():.5f})"


def test_criteria_are_not_duplicates(config, stack):
    """İki kriter neredeyse aynıysa AHP ağırlıkları çift sayılıyor demektir."""
    valid = stack.valid_mask
    for i in range(len(stack.names)):
        for j in range(i + 1, len(stack.names)):
            a, b = stack.data[i][valid], stack.data[j][valid]
            corr = float(np.corrcoef(a, b)[0, 1])
            assert abs(corr) < 0.97, (
                f"{stack.names[i]} ve {stack.names[j]} neredeyse aynı (r={corr:.3f})"
            )


def test_coverage_is_high(stack):
    """Maskeli alan yerleşim + su ile sınırlı kalmalı."""
    assert stack.coverage() > 0.90, f"geçerli piksel oranı düşük: %{100 * stack.coverage():.1f}"


# --- Risk indeksi ------------------------------------------------------------


def test_risk_index_is_in_unit_range(risk):
    finite = risk[np.isfinite(risk)]
    assert finite.min() >= 0.0
    assert finite.max() <= 1.0


def test_risk_index_uses_a_reasonable_span(risk):
    """İndeks 0-1'in çok dar bir aralığına sıkışırsa sınıflandırma anlamsızlaşır."""
    finite = risk[np.isfinite(risk)]
    assert finite.max() - finite.min() > 0.3, "risk indeksi çok dar bir aralıkta"


def test_ndvi_criterion_direction_is_correct(config, grid, stack):
    """Kritik yön kontrolü: DÜŞÜK NDVI, YÜKSEK risk skoru vermeli.

    Bu işaret ters dönerse harita tamamen tersine döner ve hiçbir şey
    çökmediği için sessizce yanlış kalır.
    """
    path = interim_path(config, "ndvi_dry.tif")
    if not path.exists():
        pytest.skip("ndvi_dry.tif yok")

    raw = read_grid_aligned(path, grid).astype("float32")
    raw = np.where(raw == np.float32(config.nodata), np.nan, raw)
    score = stack.data[list(stack.names).index("ndvi_dry")]

    valid = np.isfinite(raw) & np.isfinite(score)
    corr = float(np.corrcoef(raw[valid], score[valid])[0, 1])
    assert corr < -0.9, f"NDVI ile risk skoru arasındaki korelasyon {corr:.3f}, negatif olmalıydı"


def test_precipitation_direction_is_correct(config, grid, stack):
    """Az yağış, yüksek risk skoru vermeli."""
    path = interim_path(config, "precip_dry.tif")
    if not path.exists():
        pytest.skip("precip_dry.tif yok")

    raw = read_grid_aligned(path, grid).astype("float32")
    raw = np.where(raw == np.float32(config.nodata), np.nan, raw)
    score = stack.data[list(stack.names).index("precipitation")]

    valid = np.isfinite(raw) & np.isfinite(score)
    corr = float(np.corrcoef(raw[valid], score[valid])[0, 1])
    assert corr < -0.9, f"yağış ile risk skoru korelasyonu {corr:.3f}, negatif olmalıydı"


# --- Sınıflandırma -----------------------------------------------------------


def test_class_distribution_is_not_degenerate(config, risk):
    """Hiçbir sınıf boş kalmamalı, hiçbiri de alanın yarısını yutmamalı."""
    classes, _ = classify_risk(config, risk)
    total = int((classes > 0).sum())

    for code in range(1, config["classification"]["n_classes"] + 1):
        share = int((classes == code).sum()) / total
        assert 0.02 < share < 0.50, f"sınıf {code} payı %{100 * share:.1f} — dejenere dağılım"


def test_classification_is_reproducible(config, risk):
    """Aynı veriden iki kez aynı sınıf sınırları çıkmalı.

    Regresyon: mapclassify.NaturalBreaks global numpy RNG'sini kullanıyor;
    tohumlanmazsa sınıf sınırları çalıştırmalar arasında kayıyordu.
    """
    _, breaks_a = classify_risk(config, risk)
    _, breaks_b = classify_risk(config, risk)
    np.testing.assert_allclose(breaks_a, breaks_b)


# --- Senaryo karşılaştırması -------------------------------------------------


def test_two_scenarios_produce_different_maps(config, grid):
    """Regresyon: iki senaryo aynı slope.tif'i okuduğu için birebir aynı çıkıyordu."""
    from src.ahp import solve_from_config

    scenarios = list(config["scenarios"]["definitions"])
    risks = []
    for scenario in scenarios:
        cfg = load_config(scenario=scenario)
        if any(not cfg.criterion_path(n).exists() for n in cfg.criteria_order):
            pytest.skip(f"{scenario} kriterleri eksik")
        risks.append(weighted_overlay(load_criteria(cfg, grid), solve_from_config(cfg).weights))

    valid = np.isfinite(risks[0]) & np.isfinite(risks[1])
    mean_diff = float(np.abs(risks[0][valid] - risks[1][valid]).mean())
    assert mean_diff > 1e-4, "iki senaryo birebir aynı — senaryo geçersiz kılması uygulanmamış"


# --- Görsel çıktılar ---------------------------------------------------------


@pytest.mark.parametrize(
    "pattern",
    ["risk_map_*.png", "criteria_panel_*.png", "risk_histogram_*.png"],
)
def test_figures_exist_and_are_not_empty(config, pattern):
    figures = list(resolve(config["paths"]["figures"]).glob(pattern))
    if not figures:
        pytest.skip(f"{pattern} henüz üretilmedi")
    for figure in figures:
        assert figure.stat().st_size > 20_000, f"{figure.name} şüpheli derecede küçük"
