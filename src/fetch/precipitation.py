"""CHIRPS v2.0 yağış indirme (Adım 2).

Kaynak: Climate Hazards Center (UCSB), aylık global GeoTIFF, ~0.05° (~5.5 km).
Doğrudan HTTP; kayıt veya API anahtarı gerektirmez.

Ölçek uyarısı: CHIRPS bu AOI'yi yaklaşık 20x10 hücreyle kaplar. 30 m grid'e
yeniden örneklendiğinde katman *bölgesel* bir gradyan taşır, yerel detay değil.
Bu sınırlılık README ve doğrulama raporunda açıkça belirtilir.

Ürün global olduğu için dosyalar büyüktür (~15 MB/ay, sıkıştırılmış). Dosyalar
`data/raw/chirps/` altında önbelleğe alınır ve GDAL'in `/vsigzip/` sürücüsüyle
açılır — böylece diskte açılmış (~57 MB/ay) kopya tutulmaz.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from ..config import Config
from ..grid import TargetGrid, write_raster
from .common import interim_path, month_range, raw_path, skip_if_cached
from .common import download_file

CHIRPS_NODATA = -9999.0


def fetch_chirps(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """Referans yılların ortalama kurak dönem toplam yağışını (mm) yazar."""
    out = interim_path(config, "precip_dry.tif")
    if skip_if_cached(out, overwrite, "CHIRPS"):
        return out

    cfg = config["data_sources"]["precipitation"]
    years = config["periods"]["reference_years"]
    months = month_range(
        config["periods"]["dry_season"]["start_month"],
        config["periods"]["dry_season"]["end_month"],
    )

    print(
        f"  [CHIRPS] {len(years)} yıl x {len(months)} ay = {len(years) * len(months)} dosya "
        f"(~{15 * len(years) * len(months)} MB, bir kez indirilir)"
    )

    yearly_totals = []
    for year in years:
        monthly = [_load_month(config, grid, cfg, year, month) for month in months]
        stack = np.stack(monthly)
        # Aylardan biri bile geçersizse o yılın toplamı geçersizdir.
        total = np.where(np.isnan(stack).any(axis=0), np.nan, np.nansum(stack, axis=0))
        yearly_totals.append(total)
        print(f"      {year}: kurak dönem toplamı ortalama {np.nanmean(total):.1f} mm")

    mean_total = np.nanmean(np.stack(yearly_totals), axis=0).astype("float32")

    valid = mean_total[~np.isnan(mean_total)]
    if valid.size == 0:
        raise RuntimeError("CHIRPS tamamen boş geldi — AOI kapsamını kontrol edin")
    print(
        f"  [CHIRPS] {len(years)} yıl ortalaması: {valid.min():.1f} - {valid.max():.1f} mm "
        f"(ortalama {valid.mean():.1f} mm)"
    )

    filled = np.where(np.isnan(mean_total), config.nodata, mean_total)
    return write_raster(
        filled,
        grid,
        out,
        nodata=config.nodata,
        description=f"Kurak dönem toplam yağışı, {years[0]}-{years[-1]} ortalaması (mm)",
    )


def _load_month(config: Config, grid: TargetGrid, cfg: dict, year: int, month: int) -> np.ndarray:
    """Bir aylık global CHIRPS'i indirir (önbellekli) ve grid'e yeniden projekte eder."""
    from ..grid import reproject_to_grid

    filename = cfg["filename_pattern"].format(year=year, month=month)
    local = raw_path(config, "chirps", filename)
    if not local.exists():
        download_file(f"{cfg['base_url']}/{filename}", local, label=f"CHIRPS {year}-{month:02d}")

    with rasterio.open(f"/vsigzip/{local.as_posix()}") as src:
        array = reproject_to_grid(
            src.read(1),
            grid,
            src_crs=src.crs,
            src_transform=src.transform,
            src_nodata=src.nodata if src.nodata is not None else CHIRPS_NODATA,
            resampling="bilinear",
            dst_nodata=np.nan,
            dtype="float32",
        )

    # CHIRPS deniz/veri boşluklarını -9999 ile işaretler; yeniden örnekleme
    # sonrası kalan negatifleri de geçersiz say.
    return np.where(array < 0, np.nan, array)
