"""PROJ / GDAL veri dizinlerini bu sanal ortamın kendi kopyalarına sabitler.

Sorun: makinede kurulu başka bir GDAL/PROJ dağıtımı (ör. PostgreSQL + PostGIS)
`PROJ_LIB` ve `GDAL_DATA` ortam değişkenlerini sistem genelinde kendi
dizinlerine ayarlıyor olabilir. rasterio/pyproj tekerlekleri kendi PROJ
sürümlerini gömülü getirdiğinden, dışarıdan gelen eski bir `proj.db`
"DATABASE.LAYOUT.VERSION.MINOR = 2 whereas a number >= 6 is expected" hatasına
yol açar ve HİÇBİR CRS çözümlenemez.

Çözüm: rasterio ve pyproj içe aktarılmadan ÖNCE bu değişkenleri site-packages
içindeki gömülü dizinlere yönlendirmek. Bu yüzden `configure()` çağrısı
`src/__init__.py`'nin en üstündedir.

Devre dışı bırakmak için: AHP_KEEP_SYSTEM_PROJ=1
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def _package_dir(name: str) -> Path | None:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    return Path(list(spec.submodule_search_locations)[0])


def _bundled_proj_dir() -> Path | None:
    candidates = []
    if (rio := _package_dir("rasterio")) is not None:
        candidates.append(rio / "proj_data")
    if (pp := _package_dir("pyproj")) is not None:
        candidates.append(pp / "proj_dir" / "share" / "proj")
    return next((c for c in candidates if (c / "proj.db").is_file()), None)


def _bundled_gdal_dir() -> Path | None:
    if (rio := _package_dir("rasterio")) is None:
        return None
    gdal_data = rio / "gdal_data"
    return gdal_data if gdal_data.is_dir() else None


def configure() -> dict[str, str]:
    """Ortam değişkenlerini düzeltir; değiştirilenleri döndürür (loglanabilsin diye)."""
    if os.environ.get("AHP_KEEP_SYSTEM_PROJ"):
        return {}

    changed: dict[str, str] = {}

    if (proj_dir := _bundled_proj_dir()) is not None:
        for var in ("PROJ_LIB", "PROJ_DATA"):
            current = os.environ.get(var)
            # Zaten site-packages içini gösteriyorsa dokunma.
            if current and "site-packages" in current.replace("\\", "/"):
                continue
            os.environ[var] = str(proj_dir)
            if current != str(proj_dir):
                changed[var] = str(proj_dir)

    if (gdal_dir := _bundled_gdal_dir()) is not None:
        current = os.environ.get("GDAL_DATA")
        if not (current and "site-packages" in current.replace("\\", "/")):
            os.environ["GDAL_DATA"] = str(gdal_dir)
            if current != str(gdal_dir):
                changed["GDAL_DATA"] = str(gdal_dir)

    return changed
