"""Sentinel-2 NDVI kompozitleri (Adım 2).

Kaynak: Planetary Computer, `sentinel-2-l2a`. AOI iki MGRS tile'ına düşer
(35SNC, 35SPC) ve sahneler zaten EPSG:32635'te — yani hedef CRS'imizde.

Mimari karar: her şeyin merkezinde **aylık kompozit önbelleği** var.

    data/interim/ndvi_monthly/ndvi_YYYY_MM.tif

Kurak dönem kriteri de (Adım 3), 12 aylık animasyon da (Adım 6) aynı aylık
dosyaları kullanır. Bunun üç faydası var:
  - Uzun süren iş kesilirse kaldığı aydan devam eder.
  - 2024 Temmuz-Eylül ayları iki amaç için de tek kez hesaplanır.
  - Her ara ürün tek başına açılıp gözle kontrol edilebilir.

Bulut maskesi: SCL bandındaki bulut/gölge/kar sınıfları piksel bazında atılır,
kalan gözlemlerin medyanı alınır. Medyan, ortalamanın aksine gözden kaçan tek
tük bulut piksellerine karşı dayanıklıdır.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import Config
from ..grid import TargetGrid, read_grid_aligned, write_raster
from .common import (
    interim_path,
    load_to_grid,
    month_bounds,
    month_range,
    retry_on_expired_signature,
    search_items,
    skip_if_cached,
)

MONTHLY_DIR = "ndvi_monthly"


def fetch_ndvi_monthly(
    config: Config,
    grid: TargetGrid,
    year: int,
    month: int,
    *,
    max_cloud: float | None = None,
    overwrite: bool = False,
    index: str = "ndvi",
) -> Path:
    """Bir ayın bulutsuz medyan bitki örtüsü indeksi kompozitini üretir."""
    out = interim_path(config, MONTHLY_DIR, f"{index}_{year}_{month:02d}.tif")
    label = f"{index.upper()} {year}-{month:02d}"
    if skip_if_cached(out, overwrite, label):
        return out

    cfg = config["data_sources"]["sentinel2"]
    threshold = cfg["max_scene_cloud_cover"] if max_cloud is None else max_cloud

    def search(cloud: float) -> list:
        return search_items(
            config,
            cfg["collection"],
            datetime=month_bounds(year, month),
            query={"eo:cloud_cover": {"lt": cloud}},
        )

    items = search(threshold)

    # Bulutlu aylarda eşiği gevşet: piksel bazlı SCL maskesi zaten uygulanıyor,
    # sahne düzeyi filtre sadece gereksiz okumayı azaltmak için.
    if len(items) < cfg.get("min_scenes", 4) and threshold < 100:
        relaxed = search(100)
        if len(relaxed) > len(items):
            print(
                f"  [{label}] bulut eşiği %{threshold:g} ile {len(items)} sahne — "
                f"%100'e gevşetildi, {len(relaxed)} sahne"
            )
            items = relaxed

    if not items:
        raise RuntimeError(f"{label}: hiç Sentinel-2 sahnesi bulunamadı")

    # Saatlerce süren işlerde SAS imzaları iş bitmeden dolabilir; her deneme
    # item'ları yeniden arayıp yeniden imzalar.
    composite = retry_on_expired_signature(
        lambda: _composite(config, grid, search(threshold) or items, cfg, index=index),
        label=f"[{label}] ",
    )
    array = composite.values.astype("float32")

    gap = float(np.isnan(array).mean())
    valid = array[~np.isnan(array)]
    print(
        f"  [{label}] {len(items)} sahne -> medyan {np.median(valid):.3f} "
        f"(aralık {valid.min():.3f}..{valid.max():.3f}), boşluk %{100 * gap:.2f}"
    )
    if gap > config["data_sources"]["sentinel2"].get("max_gap_fraction", 0.20):
        print(f"      UYARI: boşluk oranı yüksek (%{100 * gap:.1f}) — bu ay bulutlu geçmiş olabilir")

    filled = np.where(np.isnan(array), config.nodata, array)
    return write_raster(
        filled, grid, out, nodata=config.nodata,
        description=f"{index.upper()} medyan kompozit {year}-{month:02d}",
    )


def baseline_offset(item, cfg: dict) -> float:
    """Bir sahneye uygulanacak radyometrik offset'i döndürür (0 veya -1000).

    Sentinel-2 işleme baseline'ı 04.00 (25 Ocak 2022) ile birlikte tüm L2A
    bantlarına BOA_ADD_OFFSET = -1000 eklendi. Planetary Computer bu offset'i
    geri almadan sunar, dolayısıyla yansımaya çevirirken biz çıkarmalıyız.

    Yıla göre değil ITEM BAZINDA karar verilir: eski tarihli sahneler de yeni
    baseline'larla yeniden işlenmiş olabilir, geçiş ayları ise iki baseline'ı
    birden içerir.
    """
    raw = item.properties.get("s2:processing_baseline")
    if raw is None:
        # Baseline bilinmiyorsa düzeltme uygulama — sessiz yanlış düzeltmektense
        # düzeltmemek yeğdir; uyarı `_partition_by_baseline` içinde basılır.
        return 0.0
    try:
        baseline = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return float(cfg["boa_add_offset"]) if baseline >= cfg["boa_offset_baseline_threshold"] else 0.0


def _partition_by_baseline(items: list, cfg: dict) -> list[tuple[float, list]]:
    """Sahneleri uygulanacak offset'e göre gruplar."""
    groups: dict[float, list] = {}
    unknown = 0
    for item in items:
        if item.properties.get("s2:processing_baseline") is None:
            unknown += 1
        groups.setdefault(baseline_offset(item, cfg), []).append(item)

    if unknown:
        print(f"      UYARI: {unknown} sahnenin baseline bilgisi yok, offset uygulanmadı")
    return sorted(groups.items())


VALID_INDICES = ("ndvi", "evi")


def _composite(config: Config, grid: TargetGrid, items: list, cfg: dict, index: str = "ndvi"):
    """SCL maskeli medyan bitki örtüsü indeksi (tembel dask, sonunda compute).

    Sahneler radyometrik offset'lerine göre ayrı ayrı yüklenir; ancak yansımaya
    çevrildikten SONRA zaman ekseninde birleştirilip medyan alınır. Karışık
    baseline'lı bir ayı tek seferde yüklemek, iki farklı ölçekteki DN'leri aynı
    kovaya atmak anlamına gelirdi.
    """
    import xarray as xr

    if index not in VALID_INDICES:
        raise ValueError(f"Bilinmeyen indeks '{index}'. Seçenekler: {VALID_INDICES}")

    bands = cfg["bands"]
    chunk = int(cfg.get("chunk_size", 1024))
    scale = float(cfg["reflectance_scale"])
    needed = [bands["red"], bands["nir"], bands["scl"]]
    if index == "evi":
        needed.insert(2, bands["blue"])

    groups = _partition_by_baseline(items, cfg)
    if len(groups) > 1:
        summary = ", ".join(f"offset {int(off)}: {len(grp)} sahne" for off, grp in groups)
        print(f"      karışık baseline ({summary})")

    parts = []
    for offset, group in groups:
        ds = load_to_grid(
            group, needed, grid,
            resampling=cfg["resampling"],
            chunks={"x": chunk, "y": chunk},
            groupby=cfg.get("groupby", "solar_day"),
        )

        valid = ~ds[bands["scl"]].isin(cfg["scl_mask_classes"])
        # Baseline offset uygulanır, ardından GERÇEK YANSIMAYA çevrilir.
        # NDVI için bölme gereksiz (oran ölçekten bağımsız) ama EVI için
        # zorunlu: paydasındaki sabit L terimi ölçeğe duyarlıdır.
        red = (ds[bands["red"]].where(valid).astype("float32") + offset) / scale
        nir = (ds[bands["nir"]].where(valid).astype("float32") + offset) / scale

        if index == "ndvi":
            denominator = nir + red
            # Offset sonrası toplam sıfır veya negatif olabilir (koyu su,
            # gölge); bu pikseller fiziksel olarak anlamsızdır, atılır.
            values = (nir - red) / denominator.where(denominator > 0)
        else:
            blue = (ds[bands["blue"]].where(valid).astype("float32") + offset) / scale
            coef = cfg["evi_coefficients"]
            denominator = nir + coef["c1"] * red - coef["c2"] * blue + coef["l"]
            values = coef["gain"] * (nir - red) / denominator.where(denominator > 0)

        # Her iki indeks de teorik olarak [-1, 1] ile sınırlıdır; dışına taşan
        # değerler atmosferik düzeltme artefaktıdır, atılır.
        parts.append(values.where((values >= -1) & (values <= 1)))

    stacked = parts[0] if len(parts) == 1 else xr.concat(parts, dim="time")
    return getattr(stacked, cfg["composite_method"])(dim="time").compute()


def fetch_ndvi_dry_composite(
    config: Config, grid: TargetGrid, *, overwrite: bool = False, index: str | None = None
) -> Path:
    """Referans yılların kurak dönem aylarından tek bir medyan indeks katmanı üretir."""
    index = index or config["data_sources"]["sentinel2"].get("vegetation_index", "ndvi")
    out = interim_path(config, f"{index}_dry.tif")
    label = f"{index.upper()} kurak"
    if skip_if_cached(out, overwrite, label):
        return out

    years = config["periods"]["reference_years"]
    months = month_range(
        config["periods"]["dry_season"]["start_month"],
        config["periods"]["dry_season"]["end_month"],
    )
    print(f"  [{label}] {len(years)} yıl x {len(months)} ay = {len(years) * len(months)} aylık kompozit")

    paths = [
        fetch_ndvi_monthly(config, grid, year, month, overwrite=overwrite, index=index)
        for year in years
        for month in months
    ]

    stack = np.stack([_read_masked(path, grid, config) for path in paths])
    composite = np.nanmedian(stack, axis=0).astype("float32")

    valid = composite[~np.isnan(composite)]
    print(
        f"  [{label}] {len(paths)} aylık kompozitin medyanı: "
        f"{valid.min():.3f} - {valid.max():.3f} (medyan {np.median(valid):.3f}), "
        f"boşluk %{100 * np.isnan(composite).mean():.2f}"
    )

    filled = np.where(np.isnan(composite), config.nodata, composite)
    return write_raster(
        filled, grid, out, nodata=config.nodata,
        description=f"Kurak dönem {index.upper()} medyanı, {years[0]}-{years[-1]}",
    )


def fetch_ndvi_timeseries(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> list[Path]:
    """Animasyon yılının 12 aylık NDVI kompozitini üretir (Adım 6 girdisi)."""
    ts = config["periods"]["timeseries"]
    year, months = ts["year"], ts["months"]
    cloud = config["data_sources"]["sentinel2"].get("timeseries_max_scene_cloud_cover", 80)

    print(f"  [NDVI serisi] {year} yılı, {len(months)} ay (sahne bulut eşiği %{cloud:g})")
    return [
        fetch_ndvi_monthly(config, grid, year, month, max_cloud=cloud, overwrite=overwrite)
        for month in months
    ]


def _read_masked(path: Path, grid: TargetGrid, config: Config) -> np.ndarray:
    """Grid'e hizalı bir katmanı okur ve nodata'yı NaN'a çevirir."""
    array = read_grid_aligned(path, grid).astype("float32")
    return np.where(array == np.float32(config.nodata), np.nan, array)
