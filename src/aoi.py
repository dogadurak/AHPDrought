"""Adım 1 — Çalışma alanı (AOI) tanımı.

Varsayılan olarak `config.yaml`'daki bbox kullanılır. `aoi.refine_with_osm`
açıksa OSM'den ilçe idari sınırları çekilip birleştirilir ve bbox ile kesiştirilir
(ağ erişimi gerektirir; hata durumunda saf bbox'a düşer).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from .config import PROJECT_ROOT, Config

WGS84 = "EPSG:4326"


def build_aoi(config: Config) -> gpd.GeoDataFrame:
    """AOI'yi WGS84'te bir GeoDataFrame olarak üretir."""
    bbox = tuple(config["aoi"]["bbox_wgs84"])
    bbox_geom = box(*bbox)

    if not config["aoi"].get("refine_with_osm", False):
        return _wrap(bbox_geom, config, source="config_bbox")

    admin = _fetch_osm_admin(config)
    if admin is None or admin.empty:
        print("[AOI] OSM sınırları alınamadı; saf bbox kullanılıyor.")
        return _wrap(bbox_geom, config, source="config_bbox")

    merged = admin.to_crs(WGS84).union_all()
    clipped = merged.intersection(bbox_geom)
    if clipped.is_empty:
        raise ValueError(
            "OSM idari sınırları ile bbox kesişmiyor. aoi.bbox_wgs84 veya "
            "aoi.osm_admin_units listesini kontrol edin."
        )
    return _wrap(clipped, config, source="osm_admin_intersect_bbox")


def _wrap(geometry, config: Config, source: str) -> gpd.GeoDataFrame:
    gdf = gpd.GeoDataFrame(
        {
            "name": [config["aoi"]["name"]],
            "source": [source],
            "target_crs": [config.crs],
        },
        geometry=[geometry],
        crs=WGS84,
    )
    return gdf


def _fetch_osm_admin(config: Config) -> gpd.GeoDataFrame | None:
    units = config["aoi"].get("osm_admin_units") or []
    if not units:
        return None
    try:
        import osmnx as ox
    except ImportError:
        print("[AOI] osmnx kurulu değil; refine_with_osm atlanıyor.")
        return None
    try:
        return ox.geocode_to_gdf(list(units))
    except Exception as exc:  # ağ hatası, bulunamayan yer adı vb.
        print(f"[AOI] OSM sorgusu başarısız ({type(exc).__name__}: {exc})")
        return None


def save_aoi(gdf: gpd.GeoDataFrame, path: str | Path) -> Path:
    out = Path(path)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GeoJSON")
    return out


def load_aoi(path: str | Path) -> gpd.GeoDataFrame:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        raise FileNotFoundError(
            f"AOI bulunamadı: {p}. Önce `python -m scripts.step01_define_grid` çalıştırın."
        )
    return gpd.read_file(p)
