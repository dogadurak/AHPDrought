"""Adım 1 — Çalışma alanı (AOI) ve ortak grid tanımı.

Projedeki her raster katman bu modüldeki `TargetGrid`'e hizalanır: aynı CRS,
aynı çözünürlük, aynı origin, aynı satır/sütun sayısı. Ağırlıklı çakıştırmanın
(Adım 5) piksel piksel doğru çalışabilmesinin ön koşulu budur.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import Affine, from_origin
from rasterio.warp import reproject, transform_bounds

from .config import PROJECT_ROOT, Config, ConfigError

_RESAMPLING_BY_NAME = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
    "average": Resampling.average,
    "mode": Resampling.mode,
    "max": Resampling.max,
    "min": Resampling.min,
}


@dataclass(frozen=True)
class TargetGrid:
    """Tüm katmanların hizalanacağı referans grid."""

    crs: str
    resolution: float
    width: int
    height: int
    # Affine parametreleri (a, b, c, d, e, f) — JSON'a serileştirilebilsin diye
    # rasterio.Affine yerine tuple tutulur.
    transform_params: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]  # (left, bottom, right, top)
    bbox_wgs84: tuple[float, float, float, float]

    @property
    def transform(self) -> Affine:
        return Affine(*self.transform_params)

    @property
    def shape(self) -> tuple[int, int]:
        return (self.height, self.width)

    @property
    def cell_count(self) -> int:
        return self.width * self.height

    @property
    def area_km2(self) -> float:
        return self.cell_count * (self.resolution**2) / 1e6

    def profile(self, dtype: str = "float32", nodata: float = -9999.0, count: int = 1) -> dict[str, Any]:
        """`rasterio.open(..., 'w', **profile)` için hazır profil."""
        return {
            "driver": "GTiff",
            "height": self.height,
            "width": self.width,
            "count": count,
            "dtype": dtype,
            "crs": self.crs,
            "transform": self.transform,
            "nodata": nodata,
            "compress": "deflate",
            # GDAL: 3 = kayan nokta öngörücüsü, 2 = yatay farklama (tamsayı)
            "predictor": 3 if dtype.startswith("float") else 2,
            "tiled": True,
            "blockxsize": 512,
            "blockysize": 512,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetGrid":
        return cls(
            crs=data["crs"],
            resolution=float(data["resolution"]),
            width=int(data["width"]),
            height=int(data["height"]),
            transform_params=tuple(data["transform_params"]),  # type: ignore[arg-type]
            bounds=tuple(data["bounds"]),  # type: ignore[arg-type]
            bbox_wgs84=tuple(data["bbox_wgs84"]),  # type: ignore[arg-type]
        )


def build_grid(config: Config, bbox_wgs84: tuple[float, float, float, float] | None = None) -> TargetGrid:
    """AOI bbox'ından ortak grid'i türetir.

    bbox WGS84'ten hedef CRS'e dönüştürülür, ardından `origin_snap` açıksa
    sınırlar çözünürlüğün tam katına DIŞA doğru yuvarlanır. Dışa yuvarlama,
    AOI'nin hiçbir köşesinin grid dışında kalmamasını garanti eder; tam kata
    hizalama ise farklı makinelerde birebir aynı grid'in üretilmesini sağlar.
    """
    bbox = tuple(bbox_wgs84 or config["aoi"]["bbox_wgs84"])
    if len(bbox) != 4:
        raise ConfigError(f"bbox 4 elemanlı olmalı: {bbox}")

    res = config.resolution
    left, bottom, right, top = transform_bounds("EPSG:4326", config.crs, *bbox, densify_pts=21)

    buffer_m = float(config["aoi"].get("buffer_m") or 0)
    if buffer_m:
        left, bottom, right, top = left - buffer_m, bottom - buffer_m, right + buffer_m, top + buffer_m

    if config["grid"].get("origin_snap", True):
        left = np.floor(left / res) * res
        bottom = np.floor(bottom / res) * res
        right = np.ceil(right / res) * res
        top = np.ceil(top / res) * res

    width = int(round((right - left) / res))
    height = int(round((top - bottom) / res))
    if width <= 0 or height <= 0:
        raise ConfigError(f"Grid boyutu geçersiz: {width}x{height} (bbox={bbox})")

    transform = from_origin(left, top, res, res)

    return TargetGrid(
        crs=config.crs,
        resolution=res,
        width=width,
        height=height,
        transform_params=(transform.a, transform.b, transform.c, transform.d, transform.e, transform.f),
        bounds=(left, bottom, right, top),
        bbox_wgs84=bbox,  # type: ignore[arg-type]
    )


def reproject_to_grid(
    source: np.ndarray | str | Path,
    grid: TargetGrid,
    *,
    src_crs: Any = None,
    src_transform: Affine | None = None,
    src_nodata: float | None = None,
    resampling: str = "bilinear",
    dst_nodata: float = -9999.0,
    dtype: str = "float32",
    band: int = 1,
) -> np.ndarray:
    """Herhangi bir raster'ı hedef grid'e yeniden projekte eder.

    `source` bir dosya yolu ise CRS/transform/nodata dosyadan okunur; numpy
    dizisi ise `src_crs` ve `src_transform` zorunludur.

    Returns:
        (grid.height, grid.width) şeklinde, boşlukları `dst_nodata` ile
        doldurulmuş dizi.
    """
    if resampling not in _RESAMPLING_BY_NAME:
        raise ValueError(
            f"Bilinmeyen resampling '{resampling}'. Seçenekler: {sorted(_RESAMPLING_BY_NAME)}"
        )

    if isinstance(source, (str, Path)):
        with rasterio.open(source) as src:
            data = src.read(band)
            src_crs = src.crs
            src_transform = src.transform
            src_nodata = src.nodata if src_nodata is None else src_nodata
    else:
        data = np.asarray(source)
        if src_crs is None or src_transform is None:
            raise ValueError("numpy dizisi verildiğinde src_crs ve src_transform zorunludur")

    destination = np.full(grid.shape, dst_nodata, dtype=dtype)

    reproject(
        source=data,
        destination=destination,
        src_transform=src_transform,
        src_crs=src_crs,
        src_nodata=src_nodata,
        dst_transform=grid.transform,
        dst_crs=grid.crs,
        dst_nodata=dst_nodata,
        resampling=_RESAMPLING_BY_NAME[resampling],
    )
    return destination


def write_raster(
    array: np.ndarray,
    grid: TargetGrid,
    path: str | Path,
    *,
    nodata: float = -9999.0,
    dtype: str = "float32",
    description: str | None = None,
) -> Path:
    """Grid'e hizalı bir diziyi sıkıştırılmış GeoTIFF olarak yazar."""
    if array.shape != grid.shape:
        raise ValueError(f"Dizi şekli {array.shape}, grid şekli {grid.shape} ile uyuşmuyor")

    out = Path(path)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(out, "w", **grid.profile(dtype=dtype, nodata=nodata)) as dst:
        dst.write(array.astype(dtype), 1)
        if description:
            dst.set_band_description(1, description)
    return out


def read_grid_aligned(path: str | Path, grid: TargetGrid, band: int = 1) -> np.ndarray:
    """Grid'e hizalı olduğu varsayılan bir raster'ı okur ve hizayı doğrular."""
    with rasterio.open(path) as src:
        if (src.height, src.width) != grid.shape:
            raise ValueError(
                f"{path}: şekil {(src.height, src.width)}, beklenen {grid.shape}. "
                "Katman ortak grid'e hizalanmamış."
            )
        if not np.allclose(np.array(src.transform)[:6], np.array(grid.transform)[:6], atol=1e-6):
            raise ValueError(f"{path}: transform ortak grid'den farklı.")
        return src.read(band, masked=False)


def save_grid_definition(grid: TargetGrid, path: str | Path) -> Path:
    out = Path(path)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        json.dump(grid.to_dict(), fh, indent=2, ensure_ascii=False)
    return out


def load_grid_definition(path: str | Path) -> TargetGrid:
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    if not p.exists():
        raise FileNotFoundError(
            f"Grid tanımı bulunamadı: {p}. Önce `python -m scripts.step01_define_grid` çalıştırın."
        )
    with p.open("r", encoding="utf-8") as fh:
        return TargetGrid.from_dict(json.load(fh))
