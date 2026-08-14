"""NDVI ve EVI hesaplamalarının testleri.

Buradaki asıl mesele bir ölçek tuzağı: NDVI bir orandır ve ölçekten
bağımsızdır, EVI ise paydasında sabit bir terim (L) taşıdığı için mutlaka
gerçek yansımayla hesaplanmalıdır. Ham DN ile hesaplanan EVI hata vermez,
sadece sessizce yanlış çıkar.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.config import load_config
from src.fetch.sentinel2 import VALID_INDICES


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def s2(config):
    return config["data_sources"]["sentinel2"]


def ndvi(red, nir):
    return (nir - red) / (nir + red)


def evi(red, nir, blue, coef):
    return coef["gain"] * (nir - red) / (nir + coef["c1"] * red - coef["c2"] * blue + coef["l"])


# --- Ölçek duyarlılığı (projenin asıl riski) ---------------------------------


def test_ndvi_is_scale_invariant():
    """Oran olduğu için DN ile de yansıma ile de aynı sonucu verir."""
    red_dn, nir_dn = 1200.0, 3000.0
    assert ndvi(red_dn, nir_dn) == pytest.approx(ndvi(red_dn / 10000, nir_dn / 10000))


def test_evi_is_not_scale_invariant(s2):
    """EVI ölçeğe DUYARLIDIR — bu yüzden yansımaya çevirmek zorunlu.

    Ham DN ile hesaplanırsa paydadaki L = 1 terimi binlerin yanında ihmal
    edilebilir kalır ve EVI, NDVI'a benzeyen ama fiziksel anlamı olmayan bir
    sayıya dönüşür.
    """
    coef = s2["evi_coefficients"]
    scale = s2["reflectance_scale"]
    red_dn, nir_dn, blue_dn = 1200.0, 3000.0, 900.0

    wrong = evi(red_dn, nir_dn, blue_dn, coef)
    correct = evi(red_dn / scale, nir_dn / scale, blue_dn / scale, coef)

    assert abs(wrong - correct) > 0.15, (
        f"ölçek hatası fark yaratmalıydı: yanlış={wrong:.4f} doğru={correct:.4f}"
    )
    assert -1 <= correct <= 1


def test_evi_denominator_uses_the_l_constant(s2):
    """L terimi kaldırılırsa sonuç değişmeli — yoksa formül yanlış kurulmuş."""
    coef = dict(s2["evi_coefficients"])
    red, nir, blue = 0.12, 0.30, 0.09

    with_l = evi(red, nir, blue, coef)
    without_l = evi(red, nir, blue, {**coef, "l": 0.0})
    assert with_l != pytest.approx(without_l)


# --- Fiziksel davranış -------------------------------------------------------


@pytest.mark.parametrize(
    "red,nir,label",
    [
        (0.30, 0.30, "çıplak toprak (kızıl ve yakın kızılötesi eşit)"),
        (0.05, 0.45, "yoğun bitki örtüsü"),
        (0.08, 0.03, "su yüzeyi"),
    ],
)
def test_both_indices_stay_in_physical_range(s2, red, nir, label):
    blue = red * 0.7
    coef = s2["evi_coefficients"]

    assert -1 <= ndvi(red, nir) <= 1, label
    assert -1 <= evi(red, nir, blue, coef) <= 1, label


def test_dense_vegetation_scores_higher_than_bare_soil(s2):
    coef = s2["evi_coefficients"]
    dense = (0.05, 0.45, 0.03)
    bare = (0.25, 0.30, 0.18)

    assert ndvi(dense[0], dense[1]) > ndvi(bare[0], bare[1])
    assert evi(*dense, coef) > evi(*bare, coef)


def test_indices_broadly_agree_but_are_not_interchangeable(s2):
    """İki indeks aynı yönü göstermeli ama birebir aynı olmamalı.

    Alt sınır (0.70): tamamen ayrışıyorlarsa biri yanlış kurulmuş demektir.
    Üst sınır (0.99): birebir aynılarsa EVI'nin mavi bant düzeltmesi
    uygulanmıyor, yani formül fiilen NDVI'a çökmüş demektir.

    Ölçülen ~0.80 değeri, EVI'nin mavi bant üzerinden atmosferik saçılmaya
    tepki vermesinden gelir — indeks seçiminin sonucu değiştirebileceğinin
    işaretidir ve `scripts/compare_vegetation_index.py` bunu gerçek veride
    ölçer.
    """
    coef = s2["evi_coefficients"]
    rng = np.random.default_rng(0)
    red = rng.uniform(0.02, 0.25, 400)
    nir = red + rng.uniform(0.0, 0.35, 400)
    blue = red * rng.uniform(0.5, 0.9, 400)

    from scipy.stats import rankdata

    a, b = ndvi(red, nir), evi(red, nir, blue, coef)
    corr = float(np.corrcoef(rankdata(a), rankdata(b))[0, 1])

    assert corr > 0.70, f"iki indeks tamamen ayrışıyor (ρ={corr:.3f}) — formül hatası olabilir"
    assert corr < 0.99, f"EVI fiilen NDVI'a çökmüş (ρ={corr:.3f}) — mavi bant düzeltmesi çalışmıyor"


# --- Konfigürasyon -----------------------------------------------------------


def test_configured_index_is_valid(s2):
    assert s2.get("vegetation_index", "ndvi") in VALID_INDICES


def test_blue_band_is_declared_for_evi(s2):
    """EVI mavi bant gerektirir; eksikse çalışma anında patlar."""
    assert "blue" in s2["bands"]
    assert s2["bands"]["blue"] in s2["resampling"]


def test_evi_coefficients_match_the_standard(s2):
    """MODIS/Sentinel-2 için standart EVI katsayıları."""
    coef = s2["evi_coefficients"]
    assert coef["gain"] == pytest.approx(2.5)
    assert coef["c1"] == pytest.approx(6.0)
    assert coef["c2"] == pytest.approx(7.5)
    assert coef["l"] == pytest.approx(1.0)


def test_reflectance_scale_is_l2a_standard(s2):
    assert s2["reflectance_scale"] == 10000
