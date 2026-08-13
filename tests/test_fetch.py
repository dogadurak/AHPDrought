"""Adım 2 veri indirme modüllerinin testleri.

Ağ gerektiren testler `@pytest.mark.network` ile işaretli ve bağlantı yoksa
otomatik atlanır; geri kalanı tamamen çevrimdışı çalışır.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.config import load_config
from src.fetch import common
from src.fetch.landcover import WORLDCOVER_NODATA
from src.fetch.lst import VALID_PLATFORMS, _filter_platform
from src.grid import build_grid


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def grid(config):
    return build_grid(config)


# Bağlantı kontrolü tests/conftest.py içinde, tembel olarak yapılır: testin
# toplanması sırasında değil, yalnızca gerçekten çalışacağı anda.
network = pytest.mark.network


# --- Çevrimdışı: yardımcı fonksiyonlar ---------------------------------------


def test_month_range_is_inclusive():
    assert common.month_range(7, 9) == [7, 8, 9]
    assert common.month_range(1, 1) == [1]


def test_month_range_rejects_wraparound():
    """Yıl sınırını aşan mevsim sessizce boş liste döndürmemeli."""
    with pytest.raises(ValueError, match="Yıl sınırını aşan"):
        common.month_range(11, 2)


def test_month_range_rejects_invalid_months():
    with pytest.raises(ValueError, match="1-12"):
        common.month_range(0, 5)


@pytest.mark.parametrize(
    "year,month,expected",
    [
        (2024, 2, "2024-02-01/2024-02-29"),  # artık yıl
        (2023, 2, "2023-02-01/2023-02-28"),
        (2024, 8, "2024-08-01/2024-08-31"),
        (2024, 9, "2024-09-01/2024-09-30"),
    ],
)
def test_month_bounds_handles_month_lengths(year, month, expected):
    """Şubat ve 30 günlük aylar doğru bitmeli — yanlış son gün sahne kaybettirir."""
    assert common.month_bounds(year, month) == expected


def test_geobox_matches_target_grid(grid):
    gb = common.geobox(grid)
    assert tuple(gb.shape) == grid.shape
    assert gb.crs.epsg == 32635
    assert gb.transform == grid.transform


def test_interim_and_raw_paths_are_inside_project(config):
    interim = common.interim_path(config, "x.tif")
    raw = common.raw_path(config, "chirps", "y.tif.gz")
    assert "interim" in interim.as_posix()
    assert "raw" in raw.as_posix()
    assert interim.parent.exists()
    assert raw.parent.exists()


def test_skip_if_cached_respects_overwrite(tmp_path):
    path = tmp_path / "a.tif"
    path.write_bytes(b"x" * 10)

    assert common.skip_if_cached(path, overwrite=False, label="t") is True
    assert common.skip_if_cached(path, overwrite=True, label="t") is False
    assert common.skip_if_cached(tmp_path / "yok.tif", overwrite=False, label="t") is False


# --- Çevrimdışı: MODIS platform ayrımı ---------------------------------------


class _FakeItem:
    def __init__(self, item_id):
        self.id = item_id


TERRA = _FakeItem("MOD11A2.A2024209.h20v05.061.2024218")
AQUA = _FakeItem("MYD11A2.A2024209.h20v05.061.2024218")


def test_platform_filter_separates_terra_and_aqua():
    """`platform` özelliği boş geldiği için ayrım id ön ekinden yapılmalı."""
    items = [TERRA, AQUA, TERRA]
    assert _filter_platform(items, "MYD11A2") == [AQUA]
    assert _filter_platform(items, "MOD11A2") == [TERRA, TERRA]
    assert _filter_platform(items, "both") == items


def test_config_lst_platform_is_valid(config):
    assert config["data_sources"]["lst"]["platform"] in VALID_PLATFORMS


# --- Çevrimdışı: konfigürasyon tutarlılığı -----------------------------------


def test_sentinel2_resampling_covers_every_band(config):
    """Kategorik SCL bandı asla sürekli yöntemle örneklenmemeli."""
    cfg = config["data_sources"]["sentinel2"]
    bands = set(cfg["bands"].values())
    resampling = cfg["resampling"]

    assert bands == set(resampling), f"resampling eksik/fazla: {bands} vs {set(resampling)}"
    assert resampling[cfg["bands"]["scl"]] in ("mode", "nearest"), (
        "SCL sınıf kodu taşır; bilinear/average ile örneklenirse anlamsız ara değerler üretir"
    )


def test_landcover_resampling_is_categorical_in_code():
    """fetch_worldcover 'mode' kullanmalı — regresyon koruması."""
    import inspect

    from src.fetch import landcover

    source = inspect.getsource(landcover.fetch_worldcover)
    assert 'resampling="mode"' in source


def test_scl_mask_covers_clouds_and_shadows(config):
    """Bulut, gölge ve kar sınıfları maskede olmalı."""
    masked = set(config["data_sources"]["sentinel2"]["scl_mask_classes"])
    for required in (3, 8, 9, 10, 11):  # gölge, bulut orta/yüksek, sirrus, kar
        assert required in masked, f"SCL sınıfı {required} maskelenmiyor"
    for kept in (4, 5, 6):  # bitki örtüsü, çıplak toprak, su
        assert kept not in masked, f"SCL sınıfı {kept} gereksiz yere maskeleniyor"


def test_chirps_url_pattern_formats_correctly(config):
    cfg = config["data_sources"]["precipitation"]
    name = cfg["filename_pattern"].format(year=2024, month=8)
    assert name == "chirps-v2.0.2024.08.tif.gz"
    assert cfg["base_url"].startswith("https://")


def test_water_tag_groups_are_queried_separately(config):
    """Etiketler tek sözlükte birleşirse boş bir grup tüm sorguyu düşürür."""
    groups = config["data_sources"]["water"]["tag_groups"]
    assert isinstance(groups, list) and len(groups) >= 2
    assert all(isinstance(g, dict) for g in groups)


# --- Ağ gerektiren testler ---------------------------------------------------


@network
def test_stac_search_finds_dem_tiles(config):
    items = common.search_items(config, config["data_sources"]["dem"]["collection"])
    assert len(items) >= 1
    assert all("data" in item.assets for item in items)


@network
def test_worldcover_items_have_no_datetime_but_have_start_datetime(config):
    """Regresyon: bu koleksiyonda `datetime` None'dır, yıl filtresi start_datetime ile."""
    items = common.search_items(config, config["data_sources"]["landcover"]["collection"])
    assert items
    assert all(item.datetime is None for item in items)
    assert all("start_datetime" in item.properties for item in items)


@network
def test_modis_collection_really_mixes_platforms(config):
    """Regresyon: koleksiyon hem Terra hem Aqua içeriyor ve `platform` boş geliyor."""
    items = common.search_items(
        config, config["data_sources"]["lst"]["collection"], datetime="2024-07-01/2024-09-30"
    )
    prefixes = {item.id.split(".")[0] for item in items}
    assert {"MOD11A2", "MYD11A2"} <= prefixes, f"beklenen iki platform, bulunan: {prefixes}"
    assert all(not item.properties.get("platform") for item in items)


@network
def test_sentinel2_scenes_are_already_in_target_crs(config):
    """AOI tek UTM zone'una düştüğü için sahneler yeniden projekte edilmeden hizalanır."""
    items = common.search_items(
        config,
        config["data_sources"]["sentinel2"]["collection"],
        datetime="2024-08-01/2024-08-31",
        query={"eo:cloud_cover": {"lt": 20}},
    )
    assert items
    assert {i.properties["proj:code"] for i in items} == {config.crs}


# --- Üretilmiş katmanların doğrulanması (varsa) ------------------------------


def _interim(config, name):
    path = common.interim_path(config, name)
    if not path.exists():
        pytest.skip(f"{name} henüz üretilmedi (önce `python -m scripts.step02_fetch_data`)")
    return path


def test_dem_layer_is_physically_plausible(config, grid):
    from src.grid import read_grid_aligned

    array = read_grid_aligned(_interim(config, "dem.tif"), grid)
    valid = array[array != config.nodata]

    assert valid.size > 0
    # Gediz ovası tabanı ~30 m, Bozdağlar zirvesi ~2160 m.
    assert -10 < valid.min() < 200, f"minimum yükseklik şüpheli: {valid.min()}"
    assert 1500 < valid.max() < 2500, f"maksimum yükseklik şüpheli: {valid.max()}"


def test_landcover_layer_has_only_known_classes(config, grid):
    from src.config import load_json
    from src.grid import read_grid_aligned

    array = read_grid_aligned(_interim(config, "landcover.tif"), grid)
    lookup = load_json(config["data_sources"]["landcover"]["lookup_file"])["classes"]

    codes = set(np.unique(array).tolist()) - {WORLDCOVER_NODATA}
    unknown = {c for c in codes if str(c) not in lookup}
    assert not unknown, f"lookup tablosunda olmayan sınıflar: {unknown}"


def test_water_layer_is_metric_and_clipped(config, grid):
    import geopandas as gpd

    path = common.interim_path(config, "water.gpkg")
    if not path.exists():
        pytest.skip("water.gpkg henüz üretilmedi")

    gdf = gpd.read_file(path)
    assert gdf.crs.to_epsg() == 32635, "mesafe hesabı için metrik CRS şart"
    assert len(gdf) > 0

    from shapely.geometry import box

    assert gdf.union_all().within(box(*grid.bounds).buffer(1))
