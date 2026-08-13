"""Eğim/bakı matematiğinin testleri (Adım 3).

Bu modülün analitik olarak bilinen sonuçları vardır: bilinen eğimli düzlemler
üzerinde eğim ve bakı tam olarak hesaplanabilir. Bakı işaret hatası (kuzey/güney
ya da doğu/batı karışması) tüm risk haritasını sessizce bozacağı için burada
her yön ayrı ayrı sınanır.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.criteria.terrain import aspect_degrees, horn_gradients, slope_degrees, southness

CELL = 30.0


def plane(rows: int = 9, cols: int = 9, *, d_east: float = 0.0, d_north: float = 0.0) -> np.ndarray:
    """Yüksekliği doğuya/kuzeye doğru sabit oranda değişen düzlem üretir.

    d_east: doğuya doğru metre başına yükseklik artışı
    d_north: kuzeye doğru metre başına yükseklik artışı
    """
    col_idx = np.arange(cols)[None, :]          # sütun doğuya artar
    row_idx = np.arange(rows)[:, None]          # satır GÜNEYE artar
    east_m = col_idx * CELL
    north_m = (rows - 1 - row_idx) * CELL
    return (100.0 + east_m * d_east + north_m * d_north).astype("float64")


# --- Gradyanlar --------------------------------------------------------------


def test_flat_surface_has_zero_gradient():
    dem = np.full((7, 7), 250.0)
    dz_dx, dz_dy = horn_gradients(dem, CELL)
    np.testing.assert_allclose(dz_dx, 0.0, atol=1e-12)
    np.testing.assert_allclose(dz_dy, 0.0, atol=1e-12)


def test_gradient_recovers_known_plane():
    """%10 doğuya, %5 kuzeye eğimli düzlemde gradyan tam olarak bilinir."""
    dem = plane(d_east=0.10, d_north=0.05)
    dz_dx, dz_dy = horn_gradients(dem, CELL)

    inner = (slice(1, -1), slice(1, -1))  # kenar doldurmasından etkilenmeyen bölge
    np.testing.assert_allclose(dz_dx[inner], 0.10, atol=1e-12)
    np.testing.assert_allclose(dz_dy[inner], 0.05, atol=1e-12)


def test_gradients_reject_bad_input():
    with pytest.raises(ValueError, match="pozitif"):
        horn_gradients(np.zeros((5, 5)), 0.0)
    with pytest.raises(ValueError, match="2 boyutlu"):
        horn_gradients(np.zeros((5, 5, 3)), CELL)


# --- Eğim --------------------------------------------------------------------


def test_flat_surface_has_zero_slope():
    assert slope_degrees(np.full((7, 7), 100.0), CELL).max() == pytest.approx(0.0, abs=1e-6)


@pytest.mark.parametrize(
    "rise,expected_deg",
    [
        (0.0, 0.0),
        (1.0, 45.0),        # 1:1 eğim = 45 derece
        (np.tan(np.radians(30)), 30.0),
        (np.tan(np.radians(60)), 60.0),
    ],
)
def test_slope_matches_arctangent(rise, expected_deg):
    dem = plane(d_east=rise)
    inner = slope_degrees(dem, CELL)[1:-1, 1:-1]
    np.testing.assert_allclose(inner, expected_deg, atol=1e-4)


def test_slope_is_independent_of_direction():
    """Aynı diklik, hangi yöne bakarsa baksın aynı eğimi vermeli."""
    values = [
        slope_degrees(plane(d_east=0.2), CELL)[1:-1, 1:-1].mean(),
        slope_degrees(plane(d_east=-0.2), CELL)[1:-1, 1:-1].mean(),
        slope_degrees(plane(d_north=0.2), CELL)[1:-1, 1:-1].mean(),
        slope_degrees(plane(d_north=-0.2), CELL)[1:-1, 1:-1].mean(),
    ]
    assert np.allclose(values, values[0], atol=1e-6)


def test_slope_scales_with_cell_size():
    """Aynı yükseklik farkı daha büyük hücrede daha küçük eğim demektir."""
    dem = plane(d_east=0.10)
    fine = slope_degrees(dem, 30.0)[1:-1, 1:-1].mean()
    coarse = slope_degrees(dem, 90.0)[1:-1, 1:-1].mean()
    assert coarse < fine


# --- Bakı --------------------------------------------------------------------


@pytest.mark.parametrize(
    "d_east,d_north,expected_aspect,yon",
    [
        (0.0, +0.10, 180.0, "kuzeye yükseliyor -> güneye bakıyor"),
        (0.0, -0.10, 0.0, "güneye yükseliyor -> kuzeye bakıyor"),
        (-0.10, 0.0, 90.0, "batıya yükseliyor -> doğuya bakıyor"),
        (+0.10, 0.0, 270.0, "doğuya yükseliyor -> batıya bakıyor"),
    ],
)
def test_aspect_points_downhill(d_east, d_north, expected_aspect, yon):
    """Bakı en dik İNİŞ yönünü göstermeli; işaret hatası burada yakalanır."""
    dem = plane(d_east=d_east, d_north=d_north)
    inner = aspect_degrees(dem, CELL)[1:-1, 1:-1]
    # 0/360 sarmalını hesaba katarak karşılaştır
    diff = np.abs((inner - expected_aspect + 180) % 360 - 180)
    assert diff.max() < 1e-3, f"{yon}: beklenen {expected_aspect}, bulunan {inner.mean():.2f}"


def test_aspect_diagonal_is_between_cardinals():
    """Kuzeydoğuya yükselen yamaç güneybatıya (225°) bakmalı."""
    dem = plane(d_east=0.10, d_north=0.10)
    inner = aspect_degrees(dem, CELL)[1:-1, 1:-1]
    np.testing.assert_allclose(inner, 225.0, atol=1e-3)


def test_aspect_stays_in_range():
    rng = np.random.default_rng(3)
    dem = rng.normal(500, 50, size=(40, 40))
    aspect = aspect_degrees(dem, CELL)
    assert aspect.min() >= 0.0
    assert aspect.max() < 360.0


# --- Southness ---------------------------------------------------------------


@pytest.mark.parametrize(
    "aspect,expected",
    [
        (0.0, 0.0),      # kuzey
        (90.0, 0.5),     # doğu
        (180.0, 1.0),    # güney
        (270.0, 0.5),    # batı
        (360.0, 0.0),    # kuzey (sarmal)
    ],
)
def test_southness_cardinal_directions(aspect, expected):
    steep = np.full((3, 3), 20.0)
    result = southness(np.full((3, 3), aspect), steep)
    np.testing.assert_allclose(result, expected, atol=1e-6)


def test_southness_is_continuous_across_north():
    """Dairesel değişkenin asıl sorunu: 359° ile 1° neredeyse aynı olmalı."""
    steep = np.full((1, 2), 20.0)
    values = southness(np.array([[359.0, 1.0]]), steep)
    assert abs(float(values[0, 0]) - float(values[0, 1])) < 1e-6


def test_southness_would_break_with_naive_minmax():
    """Karşılaştırma: ham bakıyı min-max normalize etmek komşu yönleri uçlara atar.

    Bu test kodun davranışını değil, southness'e neden ihtiyaç duyulduğunu
    belgeler — regresyon değil, gerekçe testidir.
    """
    raw = np.array([359.0, 1.0])
    naive = (raw - 0) / 360.0
    assert abs(naive[0] - naive[1]) > 0.99  # neredeyse tam zıt uçlar

    correct = southness(raw.reshape(1, 2), np.full((1, 2), 20.0))
    assert abs(float(correct[0, 0]) - float(correct[0, 1])) < 1e-6


def test_flat_pixels_get_neutral_fill():
    aspect = np.array([[123.0, 45.0]])
    slope = np.array([[0.2, 30.0]])  # ilki düz, ikincisi dik
    result = southness(aspect, slope, flat_slope_threshold_deg=1.0, flat_fill=0.5)

    assert result[0, 0] == pytest.approx(0.5)
    assert result[0, 1] != pytest.approx(0.5)


def test_southness_validates_arguments():
    with pytest.raises(ValueError, match="flat_fill"):
        southness(np.zeros((2, 2)), np.zeros((2, 2)), flat_fill=1.5)
    with pytest.raises(ValueError, match="uyuşmuyor"):
        southness(np.zeros((2, 2)), np.zeros((3, 3)))


# --- Gerçek DEM üzerinde tutarlılık -----------------------------------------


def test_real_dem_produces_plausible_terrain():
    """Üretilmiş DEM varsa: eğim aralığı ve bakı dağılımı makul olmalı."""
    from src.config import load_config
    from src.fetch.common import interim_path
    from src.grid import build_grid, read_grid_aligned

    config = load_config()
    path = interim_path(config, "dem.tif")
    if not path.exists():
        pytest.skip("dem.tif henüz üretilmedi")

    grid = build_grid(config)
    dem = read_grid_aligned(path, grid).astype("float64")
    dem = np.where(dem == config.nodata, np.nan, dem)

    slope = slope_degrees(np.nan_to_num(dem, nan=float(np.nanmean(dem))), grid.resolution)
    aspect = aspect_degrees(np.nan_to_num(dem, nan=float(np.nanmean(dem))), grid.resolution)

    assert 0 <= slope.min() < 1
    assert 20 < slope.max() < 90, f"maksimum eğim şüpheli: {slope.max():.1f}°"
    assert slope.mean() < 25, f"ortalama eğim şüpheli: {slope.mean():.1f}°"

    # Bakılar tüm yönlere dağılmalı — tek yöne yığılma işaret hatasına işaret eder.
    hist, _ = np.histogram(aspect[slope > 5], bins=8, range=(0, 360))
    share = hist / hist.sum()
    assert share.max() < 0.35, f"bakı dağılımı tek yöne yığılmış: {share.round(3)}"
    assert share.min() > 0.03, f"bazı yönler neredeyse yok: {share.round(3)}"
