"""MODIS yüzey sıcaklığı (LST) indirme (Adım 2).

Kaynak: Planetary Computer, `modis-11A2-061`, asset `LST_Day_1km`
(8 günlük kompozit, 1 km, sinüzoidal projeksiyon).

DİKKAT — platform karışımı: bu koleksiyon hem Terra (MOD11A2, ~10:30 yerel
geçiş) hem Aqua (MYD11A2, ~13:30) ürünlerini içerir ve item'ların `platform`
özelliği boş string gelir. Ayrım yalnızca item id ön ekinden yapılabilir.
İkisini karıştırmak geçiş saati farkı nedeniyle sistematik sapma yaratır;
varsayılan Aqua'dır (öğleden sonraki geçiş günlük maksimum yüzey sıcaklığına
daha yakın).

Ham veri uint16 ve 0 = dolgu değeri; ölçek katsayısı 0.02 ile Kelvin'e,
oradan °C'ye çevrilir.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import Config
from ..grid import TargetGrid, write_raster
from .common import interim_path, load_to_grid, search_items, skip_if_cached

VALID_PLATFORMS = ("MYD11A2", "MOD11A2", "both")


def fetch_lst(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """Kurak dönem ortalama gündüz LST'sini (°C) ortak grid'e yazar."""
    out = interim_path(config, "lst_dry.tif")
    if skip_if_cached(out, overwrite, "LST"):
        return out

    cfg = config["data_sources"]["lst"]
    platform = cfg.get("platform", "MYD11A2")
    if platform not in VALID_PLATFORMS:
        raise ValueError(f"lst.platform {VALID_PLATFORMS} içinden olmalı, '{platform}' verildi")

    years = config["periods"]["reference_years"]
    dry = config["periods"]["dry_season"]

    items = []
    for year in years:
        found = search_items(
            config,
            cfg["collection"],
            datetime=f"{year}-{dry['start_month']:02d}-01/{year}-{dry['end_month']:02d}-30",
        )
        items.extend(_filter_platform(found, platform))

    if not items:
        raise RuntimeError(f"{cfg['collection']}: '{platform}' için hiç item bulunamadı")

    print(
        f"  [LST] {platform}, {len(years)} yıl x kurak dönem "
        f"({dry['start_month']}-{dry['end_month']}. aylar) -> {len(items)} 8-günlük kompozit"
    )

    ds = load_to_grid(items, [cfg["asset"]], grid, resampling="bilinear", groupby="solar_day")
    raw = ds[cfg["asset"]]

    lo, hi = cfg["valid_range"]
    kelvin = raw.where((raw >= lo) & (raw <= hi)) * cfg["scale_factor"]
    celsius = kelvin - cfg["kelvin_to_celsius"]

    aggregated = getattr(celsius, cfg["aggregation"])(dim="time")
    array = aggregated.values.astype("float32")

    valid = array[~np.isnan(array)]
    if valid.size == 0:
        raise RuntimeError("LST tamamen boş geldi — platform/tarih filtresini kontrol edin")
    print(
        f"  [LST] {valid.min():.1f} - {valid.max():.1f} °C "
        f"(ortalama {valid.mean():.1f} °C), boşluk %{100 * np.isnan(array).mean():.2f}"
    )

    filled = np.where(np.isnan(array), config.nodata, array)
    return write_raster(
        filled,
        grid,
        out,
        nodata=config.nodata,
        description=f"Kurak dönem ortalama gündüz LST (°C), {platform}",
    )


def _filter_platform(items: list, platform: str) -> list:
    """Item id ön ekine göre Terra/Aqua ayrımı yapar (`platform` özelliği boş gelir)."""
    if platform == "both":
        return items
    return [item for item in items if item.id.startswith(platform)]
