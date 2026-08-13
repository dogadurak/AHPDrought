"""Veri indirme modüllerinin paylaştığı yardımcılar."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence

import requests

from ..config import PROJECT_ROOT, Config
from ..grid import TargetGrid

# Planetary Computer imzalama anahtarsızdır; yalnızca anonim kotayla sınırlıdır.
_STAC_CACHE: dict[str, Any] = {}


def stac_client(config: Config):
    """Planetary Computer STAC istemcisi (asset'ler otomatik imzalanır)."""
    endpoint = config["data_sources"]["stac_endpoint"]
    if endpoint not in _STAC_CACHE:
        import planetary_computer
        import pystac_client

        _STAC_CACHE[endpoint] = pystac_client.Client.open(
            endpoint, modifier=planetary_computer.sign_inplace
        )
    return _STAC_CACHE[endpoint]


def search_items(
    config: Config,
    collection: str,
    *,
    datetime: str | None = None,
    query: dict[str, Any] | None = None,
    bbox: Sequence[float] | None = None,
) -> list:
    """AOI kapsamında STAC araması yapar ve item listesi döndürür."""
    client = stac_client(config)
    search = client.search(
        collections=[collection],
        bbox=list(bbox or config["aoi"]["bbox_wgs84"]),
        datetime=datetime,
        query=query,
    )
    return list(search.items())


def geobox(grid: TargetGrid):
    """`TargetGrid` -> odc-geo GeoBox (odc.stac.load'un beklediği biçim)."""
    from odc.geo.geobox import GeoBox

    return GeoBox(grid.shape, grid.transform, grid.crs)


def load_to_grid(
    items: Iterable,
    bands: Sequence[str],
    grid: TargetGrid,
    *,
    resampling: str | dict[str, str] = "bilinear",
    chunks: dict[str, int] | None = None,
    groupby: str | None = None,
):
    """STAC item'larını doğrudan ortak grid'e yükler (tembel/dask destekli).

    odc-stac, COG'ların yalnızca AOI'ye düşen pencerelerini okur; bu yüzden
    sahnelerin tamamını indirmeye gerek kalmaz.
    """
    import odc.stac

    kwargs: dict[str, Any] = {
        "bands": list(bands),
        "geobox": geobox(grid),
        "resampling": resampling,
        "chunks": chunks if chunks is not None else {},
    }
    if groupby:
        kwargs["groupby"] = groupby
    return odc.stac.load(list(items), **kwargs)


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


def interim_path(config: Config, *parts: str) -> Path:
    """`data/interim/...` altında bir yol üretir ve klasörünü hazırlar."""
    out = resolve(config["paths"]["data_interim"]).joinpath(*parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def raw_path(config: Config, *parts: str) -> Path:
    out = resolve(config["paths"]["data_raw"]).joinpath(*parts)
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def skip_if_cached(path: Path, overwrite: bool, label: str) -> bool:
    """Çıktı zaten üretilmişse True döndürür (ve bunu bildirir)."""
    if path.exists() and not overwrite:
        size_mb = path.stat().st_size / 1e6
        print(f"  [{label}] önbellekten: {path.name} ({size_mb:.1f} MB)")
        return True
    return False


def download_file(
    url: str,
    dest: Path,
    *,
    overwrite: bool = False,
    timeout: int = 120,
    label: str | None = None,
) -> Path:
    """Dosyayı indirir; yarım kalan indirme bırakmamak için önce .part'a yazar."""
    label = label or dest.name
    if dest.exists() and not overwrite:
        print(f"  [{label}] önbellekten: {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")

    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        written = 0
        with tmp.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 20):
                fh.write(chunk)
                written += len(chunk)
        if total and written != total:
            tmp.unlink(missing_ok=True)
            raise IOError(f"{label}: eksik indirme ({written}/{total} bayt)")

    tmp.replace(dest)
    print(f"  [{label}] indirildi: {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def month_range(start_month: int, end_month: int) -> list[int]:
    """Kapsayıcı ay aralığı; yıl sınırını aşan aralıklar desteklenmez."""
    if not 1 <= start_month <= 12 or not 1 <= end_month <= 12:
        raise ValueError(f"Ay 1-12 aralığında olmalı: {start_month}-{end_month}")
    if end_month < start_month:
        raise ValueError(
            f"Yıl sınırını aşan mevsim aralığı desteklenmiyor: {start_month}-{end_month}"
        )
    return list(range(start_month, end_month + 1))


def month_bounds(year: int, month: int) -> str:
    """STAC `datetime` aralığı: 'YYYY-MM-01/YYYY-MM-<son gün>'."""
    import calendar

    last = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01/{year}-{month:02d}-{last:02d}"
