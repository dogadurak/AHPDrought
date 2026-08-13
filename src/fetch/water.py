"""OSM yüzey suyu vektörü indirme (Adım 2).

Kaynak: OpenStreetMap (Overpass API, `osmnx` üzerinden).

Etiket grupları AYRI AYRI sorgulanır. Nedeni: osmnx, sorgu hiç sonuç
döndürmediğinde `InsufficientResponseError` fırlatır — tek bir birleşik sorguda
AOI'de karşılığı olmayan bir etiket (ör. `landuse=reservoir`; Demirköprü
Barajı OSM'de `natural=water` olarak etiketli) tüm indirmeyi düşürürdü.

Öklid mesafe raster'ına dönüştürme Adım 3'ün işidir; burada yalnızca ham
vektör toplanır ve hedef CRS'e alınır.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from ..config import Config
from ..grid import TargetGrid
from .common import interim_path, skip_if_cached


def fetch_water_features(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """AOI'deki akarsu/göl/rezervuar geometrilerini GeoPackage olarak yazar."""
    out = interim_path(config, "water.gpkg")
    if skip_if_cached(out, overwrite, "OSM su"):
        return out

    cfg = config["data_sources"]["water"]
    bbox = tuple(config["aoi"]["bbox_wgs84"])

    frames = []
    for tags in cfg["tag_groups"]:
        frame = _query(tags, bbox)
        label = ", ".join(f"{k}={v}" for k, v in tags.items())
        if frame is None or frame.empty:
            print(f"      {label:<45} sonuç yok (atlandı)")
            continue
        counts = frame.geom_type.value_counts().to_dict()
        print(f"      {label:<45} {len(frame):>4} özellik {counts}")
        frames.append(frame)

    if not frames:
        raise RuntimeError(
            "OSM'den hiç su özelliği alınamadı. Ağ bağlantısını ve "
            "data_sources.water.tag_groups ayarını kontrol edin."
        )

    merged = gpd.GeoDataFrame(
        pd.concat([f[["geometry", "source_tags"]] for f in frames], ignore_index=True),
        crs="EPSG:4326",
    )

    # Hedef CRS'e al ve grid kapsamına kırp — mesafe hesabı metrik olmalı.
    merged = merged.to_crs(grid.crs)
    merged = merged[merged.is_valid & ~merged.is_empty]
    merged = gpd.clip(merged, box(*grid.bounds))
    merged = merged[~merged.is_empty]

    if merged.empty:
        raise RuntimeError("Su geometrileri grid kapsamıyla kesişmiyor — AOI'yi kontrol edin")

    total_length_km = merged[merged.geom_type.isin(["LineString", "MultiLineString"])].length.sum() / 1000
    total_area_km2 = merged[merged.geom_type.isin(["Polygon", "MultiPolygon"])].area.sum() / 1e6
    print(
        f"  [OSM su] {len(merged)} geometri, {total_length_km:,.0f} km akarsu, "
        f"{total_area_km2:,.1f} km² su yüzeyi"
    )

    merged.to_file(out, driver="GPKG", layer="water")
    print(f"  [OSM su] yazıldı: {out.name}")
    return out


def _query(tags: dict, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame | None:
    """Tek bir etiket grubunu sorgular; sonuç yoksa None döndürür."""
    import osmnx as ox
    from osmnx._errors import InsufficientResponseError

    try:
        frame = ox.features_from_bbox(bbox, tags)
    except InsufficientResponseError:
        return None

    frame = frame[frame.geometry.notna()].copy()
    frame["source_tags"] = ", ".join(f"{k}={v}" for k, v in tags.items())
    return frame.reset_index(drop=True)
