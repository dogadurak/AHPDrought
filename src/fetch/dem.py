"""Copernicus DEM GLO-30 indirme (Adım 2).

Kaynak: Microsoft Planetary Computer, `cop-dem-glo-30`, asset `data`.
AOI iki 1°x1° tile ile kapsanır (N38E027, N38E028); odc-stac bunları tek
mozaikte birleştirip doğrudan ortak grid'e yükler.

DEM EPSG:4326'da ve elipsoidal yükseklik (EGM2008 jeoit üzerinden ortometrik)
olarak gelir. Eğim/bakı türetmesi Adım 3'ün işidir.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import Config
from ..grid import TargetGrid, write_raster
from .common import interim_path, load_to_grid, search_items, skip_if_cached


def fetch_dem(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """AOI için DEM'i ortak grid'e hizalanmış GeoTIFF olarak yazar."""
    out = interim_path(config, "dem.tif")
    if skip_if_cached(out, overwrite, "DEM"):
        return out

    cfg = config["data_sources"]["dem"]
    items = search_items(config, cfg["collection"])
    if not items:
        raise RuntimeError(f"{cfg['collection']}: AOI için hiç tile bulunamadı")
    print(f"  [DEM] {len(items)} tile: {', '.join(i.id for i in items)}")

    ds = load_to_grid(items, ["data"], grid, resampling="bilinear")
    array = ds["data"].squeeze(drop=True).values.astype("float32")

    # GLO-30 denizleri ve veri boşluklarını çok büyük negatiflerle işaretler.
    array = np.where(array < -1000, np.nan, array)
    if np.isnan(array).all():
        raise RuntimeError("DEM tamamen boş geldi — AOI/CRS ayarlarını kontrol edin")

    nodata = config.nodata
    filled = np.where(np.isnan(array), nodata, array)

    valid = array[~np.isnan(array)]
    print(
        f"  [DEM] yükseklik {valid.min():.0f}-{valid.max():.0f} m "
        f"(ortalama {valid.mean():.0f} m), boşluk %{100 * np.isnan(array).mean():.2f}"
    )

    return write_raster(filled, grid, out, nodata=nodata, description="Copernicus DEM GLO-30 (m)")
