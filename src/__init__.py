"""AHP tabanlı tarımsal kuraklık risk haritalama sistemi.

DİKKAT: `_geoenv.configure()` çağrısı rasterio/pyproj/geopandas içe
aktarılmadan ÖNCE çalışmak zorundadır (gerekçe için `src/_geoenv.py`).
Bu yüzden import sırası burada bilinçli olarak korunur.
"""

from . import _geoenv as _geoenv

_PROJ_ENV_CHANGES = _geoenv.configure()

__version__ = "0.1.0"
