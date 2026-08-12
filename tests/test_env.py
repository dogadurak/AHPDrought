"""Coğrafi kütüphane ortamının sağlamlık testleri.

Regresyon dayanağı: geliştirme makinesinde PostgreSQL/PostGIS kurulumu
`PROJ_LIB` ve `GDAL_DATA` değişkenlerini sistem genelinde kendi eski PROJ
veritabanına ayarlamıştı; bu durumda hiçbir EPSG kodu çözümlenemiyor ve
projedeki her raster işlemi başarısız oluyordu (bkz. src/_geoenv.py).
"""

from __future__ import annotations

import os

import pytest

import src  # noqa: F401  -- içe aktarma sırasında PROJ ortamını düzeltir


def test_proj_env_points_into_the_virtualenv():
    proj_lib = os.environ.get("PROJ_LIB", "")
    assert proj_lib, "PROJ_LIB ayarlanmadı"
    assert "site-packages" in proj_lib.replace("\\", "/"), (
        f"PROJ_LIB sanal ortamın dışını gösteriyor: {proj_lib}"
    )


def test_epsg_codes_resolve():
    """CRS çözümlemesi çalışmazsa proje hiçbir adımda ilerleyemez."""
    from rasterio.crs import CRS

    for code in ("EPSG:4326", "EPSG:32635"):
        crs = CRS.from_string(code)
        assert crs.to_string() == code


def test_utm35n_is_metric_and_projected():
    from rasterio.crs import CRS

    crs = CRS.from_string("EPSG:32635")
    assert crs.is_projected
    assert crs.linear_units.lower().startswith("met")


def test_wgs84_to_utm_roundtrip_is_accurate():
    """AOI merkezinde ileri-geri dönüşüm santimetre altı hata vermeli."""
    from rasterio.warp import transform

    lon, lat = 28.1, 38.45
    xs, ys = transform("EPSG:4326", "EPSG:32635", [lon], [lat])
    back_lon, back_lat = transform("EPSG:32635", "EPSG:4326", xs, ys)

    assert back_lon[0] == pytest.approx(lon, abs=1e-9)
    assert back_lat[0] == pytest.approx(lat, abs=1e-9)


def test_geopandas_and_rasterio_share_the_same_proj():
    """geopandas (pyproj) ile rasterio (GDAL) aynı CRS'i aynı şekilde görmeli."""
    import geopandas as gpd
    from rasterio.crs import CRS
    from shapely.geometry import Point

    gs = gpd.GeoSeries([Point(28.1, 38.45)], crs="EPSG:4326").to_crs("EPSG:32635")
    assert gs.crs.to_epsg() == CRS.from_string("EPSG:32635").to_epsg() == 32635
