"""MODIS evapotranspirasyon — BAĞIMSIZ DOĞRULAMA değişkeni (Adım 7).

Kaynak: Planetary Computer, `modis-16A3GF-061` (yıllık, 500 m, boşluk
doldurulmuş MOD16/MYD16 ürünü).

DİKKAT: Bu bir AHP kriteri DEĞİLDİR ve risk indeksine girmez. Amacı,
modelin çıktısını modele hiç girmemiş bir ölçümle sınamaktır.

Kullanılan büyüklük **buharlaşma oranı** ET/PET:
  ET  = gerçekleşen evapotranspirasyon (bitkinin fiilen kullandığı su)
  PET = potansiyel evapotranspirasyon (atmosferin talep ettiği su)

Oran 1'e yakınsa bitki talebi karşılayabiliyor demektir; sıfıra yaklaştıkça
su kısıtı artar. Bu, kuraklık literatüründe "evaporative stress index" olarak
bilinen ölçünün yıllık karşılığıdır.

Neden gerçekten bağımsız: MOD16, Penman-Monteith tabanlı ayrı bir modelden
üretilir ve bu projedeki hiçbir kriter (CHIRPS yağış, Sentinel-2 NDVI, MODIS
LST, WorldCover, SoilGrids, OSM mesafeleri) onun girdisi değildir. Tek
dolaylı bağ, MOD16'nın MODIS LAI/FPAR kullanmasıdır — yani bitki örtüsü
bilgisiyle kısmi bir akrabalık vardır, sıfır değildir.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import Config
from ..grid import TargetGrid, write_raster
from .common import interim_path, load_to_grid, search_items, skip_if_cached


def fetch_et_ratio(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """Referans yılların ortalama ET/PET oranını ortak grid'e yazar."""
    out = interim_path(config, "et_pet_ratio.tif")
    if skip_if_cached(out, overwrite, "MODIS ET/PET"):
        return out

    cfg = config["data_sources"]["evapotranspiration"]
    years = config["periods"]["reference_years"]
    platform = cfg["platform"]

    items = [
        item
        for item in search_items(
            config, cfg["collection"], datetime=f"{years[0]}-01-01/{years[-1]}-12-31"
        )
        if item.id.startswith(platform)
    ]
    if not items:
        raise RuntimeError(f"{cfg['collection']}: '{platform}' için item bulunamadı")

    print(f"  [ET/PET] {platform}, {len(items)} yıllık kompozit ({years[0]}-{years[-1]})")

    ds = load_to_grid(
        items,
        [cfg["assets"]["actual"], cfg["assets"]["potential"]],
        grid,
        resampling="bilinear",
        groupby="solar_day",
    )

    threshold = cfg["fill_threshold"]
    scale = cfg["scale_factor"]
    actual = ds[cfg["assets"]["actual"]].where(lambda a: a < threshold) * scale
    potential = ds[cfg["assets"]["potential"]].where(lambda a: a < threshold) * scale

    # PET sıfıra çok yakınsa oran patlar; fiziksel olarak da anlamsızdır.
    ratio = (actual / potential.where(potential > 1.0)).mean(dim="time")
    array = ratio.values.astype("float32")

    valid = array[np.isfinite(array)]
    if valid.size == 0:
        raise RuntimeError("ET/PET tamamen boş geldi")

    mean_et = float(np.nanmean(actual.mean(dim="time").values))
    mean_pet = float(np.nanmean(potential.mean(dim="time").values))
    print(
        f"  [ET/PET] ET {mean_et:.0f} mm/yıl, PET {mean_pet:.0f} mm/yıl -> "
        f"oran {valid.min():.3f} - {valid.max():.3f} (ortalama {valid.mean():.3f})"
    )

    filled = np.where(np.isnan(array), config.nodata, array)
    return write_raster(
        filled, grid, out, nodata=config.nodata,
        description=f"ET/PET buharlaşma oranı, {years[0]}-{years[-1]} ortalaması ({platform})",
    )


def fetch_et_ratio_yearly(
    config: Config, grid: TargetGrid, *, overwrite: bool = False
) -> list[Path]:
    """Her yıl için ayrı ET/PET katmanı üretir (Adım 14 girdisi).

    Yukarıdaki `fetch_et_ratio` referans yılların ORTALAMASINI verir — bir
    iklimatoloji. Operasyonel sınama için yıl bazında değer gerekir: hangi yıl
    normalinden ne kadar saptı?

    Bu, NDVI'ya alternatif bir **etki ölçüsüdür** ve kritik farkı şudur: NDVI
    sulanan parselde kuraklıkta da yüksek kalır (çiftçi sular, yeşillik korunur),
    ama ET/PET su kısıtını doğrudan ölçer. Risk haritası ET/PET anomalisini
    öngörüp NDVI anomalisini öngörmüyorsa, sorun haritada değil ÖLÇÜDEDİR.
    """
    cfg = config["data_sources"]["evapotranspiration"]
    platform = cfg["platform"]
    start = int(cfg.get("yearly_start", 2000))
    end = int(cfg.get("yearly_end", 2024))

    print(f"  [ET/PET yıllık] {platform}, {start}-{end}")
    produced: list[Path] = []

    for year in range(start, end + 1):
        out = interim_path(config, "et_yearly", f"et_pet_{year}.tif")
        if skip_if_cached(out, overwrite, f"ET/PET {year}"):
            produced.append(out)
            continue

        items = [
            item
            for item in search_items(
                config, cfg["collection"], datetime=f"{year}-01-01/{year}-12-31"
            )
            if item.id.startswith(platform)
        ]
        if not items:
            print(f"      {year}: item yok, atlandı")
            continue

        ds = load_to_grid(
            items,
            [cfg["assets"]["actual"], cfg["assets"]["potential"]],
            grid,
            resampling="bilinear",
            groupby="solar_day",
        )
        threshold = cfg["fill_threshold"]
        scale = cfg["scale_factor"]
        actual = ds[cfg["assets"]["actual"]].where(lambda a: a < threshold) * scale
        potential = ds[cfg["assets"]["potential"]].where(lambda a: a < threshold) * scale
        ratio = (
            (actual / potential.where(potential > 1.0)).mean(dim="time").values.astype("float32")
        )

        valid = ratio[np.isfinite(ratio)]
        if valid.size == 0:
            print(f"      {year}: tamamen boş, atlandı")
            continue
        print(
            f"      {year}: ET/PET {valid.min():.3f}..{valid.max():.3f} "
            f"(ortalama {valid.mean():.3f})"
        )

        write_raster(
            np.where(np.isnan(ratio), config.nodata, ratio), grid, out,
            nodata=config.nodata, description=f"ET/PET oranı {year} ({platform})",
        )
        produced.append(out)

    if len(produced) < 15:
        raise RuntimeError(
            f"Yalnızca {len(produced)} yıl üretildi; anomali taban çizgisi için yetersiz."
        )
    print(f"  [ET/PET yıllık] {len(produced)} yıl üretildi")
    return produced
