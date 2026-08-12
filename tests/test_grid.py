"""Ortak grid (Adım 1) birim testleri."""

from __future__ import annotations

import math

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from src.config import load_config
from src.grid import (
    TargetGrid,
    build_grid,
    load_grid_definition,
    read_grid_aligned,
    reproject_to_grid,
    save_grid_definition,
    write_raster,
)


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def grid(config):
    return build_grid(config)


def _synthetic_grid(res: float = 30.0, width: int = 20, height: int = 12) -> TargetGrid:
    left, top = 480_000.0, 4_290_000.0
    t = from_origin(left, top, res, res)
    return TargetGrid(
        crs="EPSG:32635",
        resolution=res,
        width=width,
        height=height,
        transform_params=(t.a, t.b, t.c, t.d, t.e, t.f),
        bounds=(left, top - height * res, left + width * res, top),
        bbox_wgs84=(27.6, 38.2, 28.6, 38.7),
    )


# --- CRS seçimi --------------------------------------------------------------


def test_utm_zone_matches_aoi_longitude(config):
    """AOI'nin merkez boylamı, seçilen UTM zone'unun içinde kalmalı.

    Regresyon testi: proje başlangıcında CRS yanlışlıkla UTM 36N (EPSG:32636)
    olarak yazılmıştı; AOI 27.6E-28.6E aralığında olduğu için zone dışında
    kalıyor ve ciddi ölçek deformasyonu üretiyordu.
    """
    min_lon, _, max_lon, _ = config["aoi"]["bbox_wgs84"]
    center_lon = (min_lon + max_lon) / 2
    expected_zone = int(math.floor((center_lon + 180) / 6) + 1)
    expected_epsg = f"EPSG:326{expected_zone:02d}"  # kuzey yarımküre

    assert config.crs == expected_epsg, (
        f"AOI merkez boylamı {center_lon}° -> UTM zone {expected_zone}, "
        f"config ise {config.crs} diyor"
    )


def test_entire_bbox_falls_within_utm_zone(config):
    """bbox'ın her iki ucu da aynı UTM zone'unda olmalı (zone taşması yok)."""
    min_lon, _, max_lon, _ = config["aoi"]["bbox_wgs84"]
    zones = {int(math.floor((lon + 180) / 6) + 1) for lon in (min_lon, max_lon)}
    assert len(zones) == 1, f"bbox birden fazla UTM zone'una yayılıyor: {zones}"


# --- Grid geometrisi ---------------------------------------------------------


def test_grid_has_positive_dimensions(grid):
    assert grid.width > 0
    assert grid.height > 0
    assert grid.cell_count == grid.width * grid.height


def test_grid_resolution_matches_config(grid, config):
    assert grid.resolution == config.resolution
    assert grid.transform.a == pytest.approx(config.resolution)
    assert grid.transform.e == pytest.approx(-config.resolution)


def test_grid_origin_is_snapped_to_resolution(grid, config):
    """origin_snap açıkken sol-üst köşe çözünürlüğün tam katı olmalı."""
    if not config["grid"].get("origin_snap", True):
        pytest.skip("origin_snap kapalı")
    res = grid.resolution
    assert grid.transform.c % res == pytest.approx(0.0, abs=1e-6)
    assert grid.transform.f % res == pytest.approx(0.0, abs=1e-6)


def test_grid_bounds_are_consistent_with_shape(grid):
    left, bottom, right, top = grid.bounds
    assert (right - left) == pytest.approx(grid.width * grid.resolution)
    assert (top - bottom) == pytest.approx(grid.height * grid.resolution)


def test_grid_covers_the_full_aoi(grid, config):
    """Dışa yuvarlama sayesinde AOI grid sınırlarının tamamen içinde kalmalı."""
    import geopandas as gpd

    bbox = gpd.GeoSeries([box(*config["aoi"]["bbox_wgs84"])], crs="EPSG:4326")
    aoi_utm = bbox.to_crs(grid.crs).iloc[0]
    grid_poly = box(*grid.bounds)
    assert grid_poly.contains(aoi_utm)


def test_grid_size_is_plausible_for_the_pilot_area(grid):
    """Gediz alt havzası ~4000-6000 km²; 30m grid'de birkaç milyon hücre olmalı."""
    assert 2_000 < grid.area_km2 < 10_000
    assert 1e6 < grid.cell_count < 5e7


def test_grid_serialization_roundtrip(grid, tmp_path):
    path = save_grid_definition(grid, tmp_path / "grid.json")
    restored = load_grid_definition(path)
    assert restored == grid
    assert restored.transform == grid.transform


def test_missing_grid_file_gives_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="step01_define_grid"):
        load_grid_definition(tmp_path / "yok.json")


# --- Profil ------------------------------------------------------------------


def test_profile_is_valid_for_rasterio(grid, tmp_path):
    profile = grid.profile(dtype="float32", nodata=-9999.0)
    out = tmp_path / "t.tif"
    with rasterio.open(out, "w", **profile) as dst:
        dst.write(np.zeros(grid.shape, dtype="float32"), 1)

    with rasterio.open(out) as src:
        assert (src.height, src.width) == grid.shape
        assert src.nodata == -9999.0
        assert src.crs.to_string() == grid.crs


# --- Yeniden projeksiyon -----------------------------------------------------


def test_reproject_to_identical_grid_is_identity():
    g = _synthetic_grid()
    rng = np.random.default_rng(0)
    source = rng.random(g.shape).astype("float32")

    out = reproject_to_grid(
        source,
        g,
        src_crs=g.crs,
        src_transform=g.transform,
        resampling="nearest",
    )
    np.testing.assert_allclose(out, source, atol=1e-6)


def test_reproject_output_always_matches_grid_shape():
    g = _synthetic_grid()
    # Kaynak farklı çözünürlük ve farklı kapsamda
    coarse = _synthetic_grid(res=90.0, width=9, height=6)
    source = np.ones(coarse.shape, dtype="float32") * 5.0

    out = reproject_to_grid(
        source, g, src_crs=coarse.crs, src_transform=coarse.transform, resampling="bilinear"
    )
    assert out.shape == g.shape


def test_reproject_rejects_unknown_resampling():
    g = _synthetic_grid()
    with pytest.raises(ValueError, match="resampling"):
        reproject_to_grid(np.zeros(g.shape), g, src_crs=g.crs, src_transform=g.transform, resampling="sihirli")


def test_reproject_requires_crs_for_arrays():
    g = _synthetic_grid()
    with pytest.raises(ValueError, match="src_crs"):
        reproject_to_grid(np.zeros(g.shape), g)


# --- G/Ç ---------------------------------------------------------------------


def test_write_and_read_roundtrip(tmp_path):
    g = _synthetic_grid()
    rng = np.random.default_rng(1)
    array = rng.random(g.shape).astype("float32")

    path = write_raster(array, g, tmp_path / "out.tif", description="test")
    read_back = read_grid_aligned(path, g)
    np.testing.assert_allclose(read_back, array, atol=1e-6)


def test_write_rejects_misaligned_array(tmp_path):
    g = _synthetic_grid()
    with pytest.raises(ValueError, match="uyuşmuyor"):
        write_raster(np.zeros((5, 5), dtype="float32"), g, tmp_path / "bad.tif")


def test_read_rejects_misaligned_raster(tmp_path):
    g = _synthetic_grid()
    other = _synthetic_grid(width=10, height=10)
    write_raster(np.zeros(other.shape, dtype="float32"), other, tmp_path / "other.tif")

    with pytest.raises(ValueError, match="hizalanmamış"):
        read_grid_aligned(tmp_path / "other.tif", g)
