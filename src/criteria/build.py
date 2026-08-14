"""Kriter katmanlarının üretimi ve normalizasyonu (Adım 3).

Girdi:  `data/interim/`  — Adım 2'nin ham, grid'e hizalanmış katmanları
Çıktı:  `data/processed/criteria/<kriter>.tif` — 0-1 risk skoru (1 = en riskli)

Ara türevler (eğim, bakı, mesafe) da `data/interim/` altına yazılır; böylece
normalize edilmiş skorun yanında ham fiziksel değer de gözle kontrol edilebilir.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import Config
from ..fetch.common import interim_path, resolve
from ..grid import TargetGrid, read_grid_aligned, write_raster
from .distance import build_distance_raster
from .landcover_score import landcover_susceptibility
from .normalize import describe, normalize_criterion
from .terrain import aspect_degrees, slope_degrees, southness


def build_all(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> dict[str, Path]:
    """config.yaml'da tanımlı tüm kriterleri üretir."""
    outputs: dict[str, Path] = {}
    for name in config.criteria_order:
        outputs[name] = build_criterion(name, config, grid, overwrite=overwrite)
    return outputs


def build_criterion(
    name: str, config: Config, grid: TargetGrid, *, overwrite: bool = False
) -> Path:
    """Tek bir kriteri ham değerden 0-1 risk skoruna kadar üretir."""
    out = config.criterion_path(name)
    out.parent.mkdir(parents=True, exist_ok=True)

    spec = config.criterion(name)
    scenario_note = f" (senaryoya bağlı: {config.scenario})" if config.is_scenario_dependent(name) else ""
    print(f"\n  [{name}] {spec['label']}{scenario_note}")

    if out.exists() and not overwrite:
        print(f"      önbellekten: {out.name}")
        return out

    builder = _BUILDERS.get(name)
    if builder is None:
        raise KeyError(
            f"'{name}' kriteri için üretici tanımlı değil. "
            f"src/criteria/build.py içindeki _BUILDERS sözlüğüne ekleyin."
        )

    raw = builder(config, grid)
    direction = "yüksek değer = yüksek risk" if spec["higher_is_riskier"] else "DÜŞÜK değer = yüksek risk"
    print(f"      ham: {_raw_summary(raw)} [{spec['unit']}]  ({direction})")

    scored = normalize_criterion(raw, spec, name=name)
    print(f"      skor: {describe(scored)}")

    filled = np.where(np.isnan(scored), config.nodata, scored)
    return write_raster(
        filled,
        grid,
        out,
        nodata=config.nodata,
        description=f"{spec['label']} — 0-1 kuraklık risk skoru",
    )


# --- Ham kriter üreticileri --------------------------------------------------


def _read_interim(config: Config, grid: TargetGrid, filename: str) -> np.ndarray:
    """Adım 2 çıktısını okur ve nodata'yı NaN'a çevirir."""
    path = interim_path(config, filename)
    if not path.exists():
        raise FileNotFoundError(
            f"{filename} bulunamadı. Önce `python -m scripts.step02_fetch_data` çalıştırın."
        )
    array = read_grid_aligned(path, grid).astype("float64")
    return np.where(array == np.float64(config.nodata), np.nan, array)


def _precipitation(config: Config, grid: TargetGrid) -> np.ndarray:
    return _read_interim(config, grid, "precip_dry.tif")


def _ndvi_dry(config: Config, grid: TargetGrid) -> np.ndarray:
    """Kurak dönem bitki örtüsü indeksi.

    Hangi indeksin kullanıldığı `data_sources.sentinel2.vegetation_index` ile
    seçilir (ndvi | evi). Kriter anahtarı geçmişe dönük uyum için `ndvi_dry`
    kalır; iki indeksin sonuca etkisi
    `python -m scripts.compare_vegetation_index` ile karşılaştırılabilir.
    """
    index = config["data_sources"]["sentinel2"].get("vegetation_index", "ndvi")
    return _read_interim(config, grid, f"{index}_dry.tif")


def _lst(config: Config, grid: TargetGrid) -> np.ndarray:
    return _read_interim(config, grid, "lst_dry.tif")


def _landcover(config: Config, grid: TargetGrid) -> np.ndarray:
    path = interim_path(config, "landcover.tif")
    if not path.exists():
        raise FileNotFoundError("landcover.tif bulunamadı. Önce Adım 2'yi çalıştırın.")
    codes = read_grid_aligned(path, grid)
    return landcover_susceptibility(codes, config).astype("float64")


def _distance_to_water(config: Config, grid: TargetGrid) -> np.ndarray:
    return _distance_from_vector(
        config, grid,
        source="water.gpkg",
        output="distance_to_water.tif",
        description="En yakın doğal yüzey suyuna Öklid mesafesi (m)",
    )


def _irrigation_access(config: Config, grid: TargetGrid) -> np.ndarray:
    return _distance_from_vector(
        config, grid,
        source="irrigation.gpkg",
        output="distance_to_irrigation.tif",
        description="En yakın sulama altyapısına Öklid mesafesi (m)",
    )


def _distance_from_vector(
    config: Config, grid: TargetGrid, *, source: str, output: str, description: str
) -> np.ndarray:
    import geopandas as gpd

    path = interim_path(config, source)
    if not path.exists():
        raise FileNotFoundError(f"{source} bulunamadı. Önce Adım 2'yi çalıştırın.")

    distance = build_distance_raster(gpd.read_file(path), grid)
    write_raster(
        distance, grid, interim_path(config, output),
        nodata=config.nodata, description=description,
    )
    return distance.astype("float64")


def _soil_awc(config: Config, grid: TargetGrid) -> np.ndarray:
    return _read_interim(config, grid, "soil_awc.tif")


def _slope(config: Config, grid: TargetGrid) -> np.ndarray:
    dem = _dem_filled(config, grid)
    slope = slope_degrees(dem, grid.resolution)
    write_raster(
        slope, grid, interim_path(config, "slope.tif"),
        nodata=config.nodata, description="Eğim (derece)",
    )
    return slope.astype("float64")


def _aspect(config: Config, grid: TargetGrid) -> np.ndarray:
    spec = config.criterion("aspect")
    dem = _dem_filled(config, grid)

    aspect = aspect_degrees(dem, grid.resolution)
    slope = slope_degrees(dem, grid.resolution)
    score = southness(
        aspect,
        slope,
        flat_slope_threshold_deg=float(spec["flat_slope_threshold_deg"]),
        flat_fill=float(spec["flat_fill"]),
    )

    write_raster(
        aspect, grid, interim_path(config, "aspect.tif"),
        nodata=config.nodata, description="Bakı (derece, kuzeyden saat yönünde)",
    )
    flat_share = 100 * float((slope < spec["flat_slope_threshold_deg"]).mean())
    print(f"      düz kabul edilen (eğim < {spec['flat_slope_threshold_deg']}°) alan: %{flat_share:.1f}")
    return score.astype("float64")


def _dem_filled(config: Config, grid: TargetGrid) -> np.ndarray:
    """DEM'i okur; eğim/bakı operatörü NaN yayacağı için boşlukları doldurur."""
    dem = _read_interim(config, grid, "dem.tif")
    gaps = np.isnan(dem)
    if gaps.any():
        print(f"      DEM boşluğu %{100 * gaps.mean():.3f} ortalamayla dolduruldu")
        dem = np.where(gaps, np.nanmean(dem), dem)
    return dem


_BUILDERS = {
    "precipitation": _precipitation,
    "irrigation_access": _irrigation_access,
    "ndvi_dry": _ndvi_dry,
    "soil_awc": _soil_awc,
    "lst": _lst,
    "landcover": _landcover,
    "distance_to_water": _distance_to_water,
    "slope": _slope,
    "aspect": _aspect,
}


def _raw_summary(array: np.ndarray) -> str:
    finite = array[np.isfinite(array)]
    if finite.size == 0:
        return "geçerli piksel yok"
    return f"{finite.min():.4g} .. {finite.max():.4g} (ortalama {finite.mean():.4g})"
