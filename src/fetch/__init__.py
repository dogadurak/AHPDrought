"""Adım 2 — Veri indirme modülleri.

Her kaynak ayrı, tek başına çalıştırılabilir ve test edilebilir bir fonksiyondur.
Hepsi ortak sözleşmeyi izler:

    fetch_x(config, grid, *, overwrite=False) -> Path

Çıktı her zaman `data/interim/` altına, ortak grid'e hizalanmış olarak yazılır.
Dosya zaten varsa ve `overwrite=False` ise indirme atlanır — bu sayede uzun
süren Sentinel-2 işi kesilse bile kaldığı yerden devam edebilir.

Ham (grid'e hizalanmamış) değerler burada üretilir; 0-1 normalizasyonu ve
kriter dönüşümleri Adım 3'ün işidir.
"""

from .dem import fetch_dem
from .landcover import fetch_worldcover
from .lst import fetch_lst
from .precipitation import fetch_chirps
from .sentinel2 import fetch_ndvi_dry_composite, fetch_ndvi_monthly, fetch_ndvi_timeseries
from .water import fetch_water_features

__all__ = [
    "fetch_dem",
    "fetch_worldcover",
    "fetch_lst",
    "fetch_chirps",
    "fetch_ndvi_monthly",
    "fetch_ndvi_dry_composite",
    "fetch_ndvi_timeseries",
    "fetch_water_features",
]
