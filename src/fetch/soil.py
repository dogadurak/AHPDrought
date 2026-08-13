"""SoilGrids toprak su tutma kapasitesi (Adım 2).

Kaynak: ISRIC SoilGrids v2.0, WCS servisi (250 m, kayıt/anahtar gerekmez).

Hesaplanan büyüklük **bitkiye yarayışlı su kapasitesi** (available water
capacity, AWC):

    AWC = wv0033 − wv1500
        = (33 kPa'daki su içeriği) − (1500 kPa'daki su içeriği)
        = tarla kapasitesi − solma noktası

Yani bitkinin kökleriyle gerçekten çekebileceği su. Kuraklık dayanımının
toprak tarafındaki doğrudan karşılığıdır: aynı yağışı alan iki parselden
AWC'si yüksek olanı kurak dönemi daha uzun taşır.

Kök bölgesi 0-30 cm alınır ve katmanlar kalınlıklarıyla ağırlıklı ortalanır
(0-5, 5-15, 15-30 cm). Yüzeydeki 5 cm'i tek başına kullanmak, derin köklü
bağ ve zeytinliğin gerçek su deposunu görmezden gelirdi.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import rasterio
import requests

from ..config import Config
from ..grid import TargetGrid, reproject_to_grid, write_raster
from .common import interim_path, raw_path, skip_if_cached


def fetch_soil_awc(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """0-30 cm yarayışlı su kapasitesini ortak grid'e hizalanmış olarak yazar."""
    out = interim_path(config, "soil_awc.tif")
    if skip_if_cached(out, overwrite, "SoilGrids"):
        return out

    cfg = config["data_sources"]["soil"]
    depths = cfg["depths"]
    total_thickness = sum(d["thickness_cm"] for d in depths)

    print(
        f"  [SoilGrids] {len(depths)} derinlik katmanı x 2 özellik "
        f"(tarla kapasitesi, solma noktası), 0-{total_thickness} cm"
    )

    weighted_sum = np.zeros(grid.shape, dtype="float64")
    weight_total = np.zeros(grid.shape, dtype="float64")

    for depth in depths:
        label, thickness = depth["label"], depth["thickness_cm"]

        field = _layer(config, grid, cfg["field_capacity_map"], label)
        wilting = _layer(config, grid, cfg["wilting_point_map"], label)

        awc = field - wilting
        # Solma noktası tarla kapasitesini aşamaz; aşıyorsa veri hatalıdır.
        awc = np.where(awc < 0, np.nan, awc)

        valid = np.isfinite(awc)
        weighted_sum[valid] += awc[valid] * thickness
        weight_total[valid] += thickness

        print(
            f"      {label:8} AWC {np.nanmin(awc):.3f}-{np.nanmax(awc):.3f} "
            f"(ortalama {np.nanmean(awc):.3f} cm3/cm3), boşluk %{100 * (~valid).mean():.2f}"
        )

    with np.errstate(invalid="ignore", divide="ignore"):
        awc = np.where(weight_total > 0, weighted_sum / weight_total, np.nan)

    valid = awc[np.isfinite(awc)]
    if valid.size == 0:
        raise RuntimeError("SoilGrids katmanı tamamen boş geldi")
    print(
        f"  [SoilGrids] 0-{total_thickness} cm ağırlıklı AWC: "
        f"{valid.min():.3f} - {valid.max():.3f} cm3/cm3 (ortalama {valid.mean():.3f}), "
        f"boşluk %{100 * np.isnan(awc).mean():.2f}"
    )

    filled = np.where(np.isnan(awc), config.nodata, awc).astype("float32")
    return write_raster(
        filled, grid, out, nodata=config.nodata,
        description=f"Yarayışlı su kapasitesi 0-{total_thickness} cm (cm3/cm3)",
    )


def _layer(config: Config, grid: TargetGrid, map_name: str, depth_label: str) -> np.ndarray:
    """Tek bir SoilGrids katmanını indirir (önbellekli) ve grid'e projekte eder."""
    cfg = config["data_sources"]["soil"]
    coverage = f"{map_name}_{depth_label}_mean"
    local = raw_path(config, "soilgrids", f"{coverage}.tif")

    if not local.exists():
        content = _download_coverage(config, cfg, map_name, coverage)
        local.write_bytes(content)
        print(f"      indirildi: {coverage}.tif ({len(content) / 1e6:.2f} MB)")

    with rasterio.open(local) as src:
        raw = src.read(1).astype("float64")
        nodata = cfg["nodata_value"]
        raw = np.where(raw == nodata, np.nan, raw)

        return reproject_to_grid(
            raw * cfg["scale_factor"],
            grid,
            src_crs=src.crs,
            src_transform=src.transform,
            src_nodata=np.nan,
            resampling="bilinear",
            dst_nodata=np.nan,
            dtype="float32",
        ).astype("float64")


def _download_coverage(config: Config, cfg: dict, map_name: str, coverage: str) -> bytes:
    """WCS GetCoverage isteğiyle AOI penceresini indirir."""
    min_lon, min_lat, max_lon, max_lat = config["aoi"]["bbox_wgs84"]
    wgs84 = "http://www.opengis.net/def/crs/EPSG/0/4326"

    response = requests.get(
        cfg["base_url"],
        params={
            "map": f"/map/{map_name}.map",
            "SERVICE": "WCS",
            "VERSION": "2.0.1",
            "REQUEST": "GetCoverage",
            "COVERAGEID": coverage,
            "FORMAT": "image/tiff",
            "SUBSET": [f"X({min_lon},{max_lon})", f"Y({min_lat},{max_lat})"],
            "SUBSETTINGCRS": wgs84,
            "OUTPUTCRS": wgs84,
        },
        timeout=300,
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "tiff" not in content_type.lower() or len(response.content) < 1000:
        raise RuntimeError(
            f"{coverage}: beklenen GeoTIFF gelmedi (Content-Type={content_type}, "
            f"{len(response.content)} bayt). Yanıt: {response.text[:300]}"
        )
    return response.content
