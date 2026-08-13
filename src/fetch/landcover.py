"""ESA WorldCover arazi örtüsü indirme (Adım 2).

Kaynak: Planetary Computer, `esa-worldcover`, asset `map` (10 m, 11 sınıf).

İki tuzak:
  1. Bu koleksiyonun item'larında `datetime` alanı **None**'dır; yıl filtresi
     `start_datetime` özelliği üzerinden yapılmalıdır.
  2. Sınıf kodları kategoriktir (10, 20, ... 100) — yeniden örnekleme mutlaka
     `mode` (çoğunluk) ile yapılmalı, asla bilinear ile değil.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ..config import Config, load_json
from ..grid import TargetGrid, write_raster
from .common import interim_path, load_to_grid, search_items, skip_if_cached

WORLDCOVER_NODATA = 0


def fetch_worldcover(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """Arazi örtüsü sınıf kodlarını ortak grid'e hizalanmış uint8 olarak yazar."""
    out = interim_path(config, "landcover.tif")
    if skip_if_cached(out, overwrite, "WorldCover"):
        return out

    cfg = config["data_sources"]["landcover"]
    year = str(cfg["year"])

    items = [
        item
        for item in search_items(config, cfg["collection"])
        if str(item.properties.get("start_datetime", "")).startswith(year)
    ]
    if not items:
        available = sorted(
            str(i.properties.get("start_datetime", ""))[:4]
            for i in search_items(config, cfg["collection"])
        )
        raise RuntimeError(
            f"WorldCover {year} için tile bulunamadı. Mevcut yıllar: {sorted(set(available))}"
        )
    print(f"  [WorldCover] {year}, {len(items)} tile: {', '.join(i.id for i in items)}")

    ds = load_to_grid(items, [cfg["asset"]], grid, resampling="mode")
    array = ds[cfg["asset"]].squeeze(drop=True).values.astype("uint8")

    _report_classes(config, array)

    return write_raster(
        array,
        grid,
        out,
        nodata=WORLDCOVER_NODATA,
        dtype="uint8",
        description=f"ESA WorldCover {year} sınıf kodu",
    )


def _report_classes(config: Config, array: np.ndarray) -> None:
    """Bulunan sınıfları lookup tablosuyla karşılaştırıp özet basar."""
    lookup = load_json(config["data_sources"]["landcover"]["lookup_file"])["classes"]
    codes, counts = np.unique(array, return_counts=True)
    total = counts.sum()

    unknown = [int(c) for c in codes if c != WORLDCOVER_NODATA and str(int(c)) not in lookup]
    for code, count in zip(codes.tolist(), counts.tolist()):
        if code == WORLDCOVER_NODATA:
            continue
        entry = lookup.get(str(code), {})
        name = entry.get("name", "BİLİNMEYEN")
        score = entry.get("score")
        score_text = "maskeli" if score is None else f"skor {score:.2f}"
        print(f"      {code:>3}  {name:<28} %{100 * count / total:5.1f}  ({score_text})")

    if unknown:
        raise RuntimeError(
            f"Lookup tablosunda karşılığı olmayan WorldCover sınıfları: {unknown}. "
            f"{config['data_sources']['landcover']['lookup_file']} dosyasını güncelleyin."
        )
