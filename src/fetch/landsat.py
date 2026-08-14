"""Landsat 5 kurak dönem NDVI kompozitleri — tarihsel kuraklıklar için.

## Neden gerekli

Risk haritasının operasyonel sınaması, elimizdeki 9 yılda (2017-2025) yalnızca
**bir** kurak yıl olduğu için karara bağlanamıyordu. Oysa 68 yıllık yağış
kaydında havzanın en şiddetli kuraklıkları **1989-01 – 1991-02 (26 ay)** ve
**2007 (11 ay)** — ikisi de Sentinel-2'den (2015) önce.

Landsat 5 arşivi 1984-2011'i kapsıyor ve **30 m** çözünürlükte, yani projenin
grid'iyle birebir aynı. Bu, haritayı gerçek stres altında sınamanın tek yolu.

## Neden yalnızca Landsat 5

Landsat 5 (TM), 7 (ETM+) ve 8/9 (OLI) farklı bant genişliklerine sahiptir ve
aynı yüzey için biraz farklı NDVI üretirler. Tek sensöre bağlı kalmak,
uyumlulaştırma katsayılarına ihtiyaç bırakmaz ve yıllar arası karşılaştırmayı
temiz tutar. Landsat 5, 1984-2011 arasıyla ilgilendiğimiz iki büyük kuraklığı
da (1989-91, 2007) kapsıyor.

Ek olarak Landsat 7'nin 2003 sonrası SLC arızası şeritli boşluklar üretir;
dışarıda bırakmak bu sorunu da ortadan kaldırır.

## İki tuzak (ikisi de STAC metadatasında yazılı, tahmin edilmiyor)

1. **Ölçekleme.** Collection-2 Level-2 yüzey yansıması `DN * 2.75e-05 - 0.2`
   ile elde edilir. Ham DN ile NDVI hesaplamak sessizce yanlış sonuç verir
   (Sentinel-2'deki baseline offset hatasının Landsat karşılığı).
2. **Dolgu değeri.** `nodata = 0`. Ölçekleme ÖNCE maskelenmezse dolgu
   pikselleri -0.2 yansımaya dönüşür ve istatistikleri kirletir.

## Dönemler karıştırılmamalı

Ölçülen: 1990 kurak dönem NDVI medyanı ~0.13, Sentinel-2 döneminde aynı mevsim
~0.45. Bu fark yalnızca kuraklıktan gelmiyor — sensör farkı ve 35 yılda genişleyen
sulu tarım da içinde. Dolayısıyla anomali **Landsat döneminin kendi içinde**
hesaplanır; Landsat hedef yılı Sentinel taban çizgisiyle karşılaştırılmaz.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import Config
from ..grid import TargetGrid, write_raster
from .common import (
    interim_path,
    load_to_grid,
    month_range,
    retry_on_expired_signature,
    search_items,
    skip_if_cached,
)

LANDSAT_DIR = "landsat_ndvi"

# Collection-2 QA_PIXEL bit anlamları (USGS). Maskelenecekler:
#   0 dolgu, 1 genişletilmiş bulut, 3 bulut, 4 bulut gölgesi, 5 kar/buz
QA_MASK_BITS = (0, 1, 3, 4, 5)


def fetch_landsat_ndvi_year(
    config: Config,
    grid: TargetGrid,
    year: int,
    *,
    overwrite: bool = False,
) -> Path:
    """Bir yılın kurak dönem medyan NDVI kompozitini üretir (Landsat 5)."""
    out = interim_path(config, LANDSAT_DIR, f"ndvi_{year}.tif")
    label = f"Landsat {year}"
    if skip_if_cached(out, overwrite, label):
        return out

    cfg = config["data_sources"]["landsat"]
    dry = config["periods"]["dry_season"]
    months = month_range(dry["start_month"], dry["end_month"])
    window = f"{year}-{months[0]:02d}-01/{year}-{months[-1]:02d}-30"

    def search() -> list:
        found = search_items(
            config, cfg["collection"], datetime=window,
            query={"eo:cloud_cover": {"lt": cfg["max_scene_cloud_cover"]}},
        )
        return [i for i in found if i.properties.get("platform") == cfg["platform"]]

    items = search()
    if len(items) < cfg.get("min_scenes", 6):
        raise RuntimeError(
            f"{label}: yalnızca {len(items)} sahne bulundu "
            f"(en az {cfg.get('min_scenes', 6)} gerekir)"
        )

    composite = retry_on_expired_signature(
        lambda: _composite(config, grid, search() or items, cfg), label=f"[{label}] "
    )
    array = composite.astype("float32")

    valid = array[np.isfinite(array)]
    gap = float(np.isnan(array).mean())
    print(
        f"  [{label}] {len(items)} sahne -> medyan {np.median(valid):.3f} "
        f"(aralık {valid.min():.3f}..{valid.max():.3f}), boşluk %{100 * gap:.2f}"
    )
    if gap > cfg.get("max_gap_fraction", 0.15):
        print(f"      UYARI: boşluk %{100 * gap:.1f} — bu yıl seyrek örneklenmiş olabilir")

    filled = np.where(np.isnan(array), config.nodata, array)
    return write_raster(
        filled, grid, out, nodata=config.nodata,
        description=f"Landsat 5 kurak dönem NDVI medyanı {year}",
    )


def _composite(config: Config, grid: TargetGrid, items: list, cfg: dict) -> np.ndarray:
    """QA maskeli, ölçeklenmiş medyan NDVI."""
    bands = cfg["bands"]
    chunk = int(cfg.get("chunk_size", 1024))

    ds = load_to_grid(
        items,
        [bands["red"], bands["nir"], bands["qa"]],
        grid,
        resampling=cfg["resampling"],
        chunks={"x": chunk, "y": chunk},
        groupby=cfg.get("groupby", "solar_day"),
    )

    red_raw = ds[bands["red"]]
    nir_raw = ds[bands["nir"]]
    qa = ds[bands["qa"]]

    # Ölçek/offset item metadatasından okunur — sabit yazılmaz.
    scale, offset, nodata = _scaling(items[0], bands["red"])

    quality_ok = _qa_valid(qa)
    # DOLGU MASKESİ ÖLÇEKLEMEDEN ÖNCE: aksi halde 0 -> -0.2 yansımaya döner.
    data_ok = (red_raw != nodata) & (nir_raw != nodata)
    keep = quality_ok & data_ok

    red = red_raw.where(keep).astype("float32") * scale + offset
    nir = nir_raw.where(keep).astype("float32") * scale + offset

    denominator = nir + red
    ndvi = (nir - red) / denominator.where(denominator > 0)
    ndvi = ndvi.where((ndvi >= -1) & (ndvi <= 1))

    return ndvi.median(dim="time").compute().values


def _scaling(item, band: str) -> tuple[float, float, float]:
    """Ölçek, offset ve dolgu değerini STAC metadatasından okur."""
    raster = item.assets[band].extra_fields.get("raster:bands")
    if not raster:
        raise RuntimeError(
            f"{item.id}: '{band}' için raster:bands metadatası yok — "
            "ölçek katsayısı tahmin edilemez"
        )
    info = raster[0]
    return (
        float(info.get("scale", 1.0)),
        float(info.get("offset", 0.0)),
        float(info.get("nodata", 0)),
    )


def _qa_valid(qa):
    """QA_PIXEL bit maskesinden geçerli piksel maskesi üretir."""
    valid = None
    for bit in QA_MASK_BITS:
        flag = (qa >> bit) & 1
        valid = (flag == 0) if valid is None else (valid & (flag == 0))
    return valid


def fetch_landsat_series(
    config: Config,
    grid: TargetGrid,
    *,
    overwrite: bool = False,
) -> list[Path]:
    """Landsat döneminin tüm yıllık kurak dönem kompozitlerini üretir."""
    cfg = config["data_sources"]["landsat"]
    years = list(range(cfg["start_year"], cfg["end_year"] + 1))
    print(f"  [Landsat] {cfg['platform']}, {years[0]}-{years[-1]} ({len(years)} yıl)")

    produced, failed = [], []
    for year in years:
        try:
            produced.append(fetch_landsat_ndvi_year(config, grid, year, overwrite=overwrite))
        except Exception as exc:
            failed.append((year, f"{type(exc).__name__}: {exc}"))
            print(f"  [Landsat {year}] atlandı — {type(exc).__name__}: {exc}")

    print(f"  [Landsat] {len(produced)}/{len(years)} yıl üretildi")
    if failed:
        print(f"      atlanan yıllar: {[y for y, _ in failed]}")
    if len(produced) < 15:
        raise RuntimeError(
            f"Yalnızca {len(produced)} yıl üretilebildi; anomali taban çizgisi için yetersiz."
        )
    return produced
