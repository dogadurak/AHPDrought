"""AHP tabanlı tarımsal kuraklık risk haritalama sistemi.

DİKKAT: `_geoenv.configure()` çağrısı rasterio/pyproj/geopandas içe
aktarılmadan ÖNCE çalışmak zorundadır (gerekçe için `src/_geoenv.py`).
Bu yüzden import sırası burada bilinçli olarak korunur.
"""

import sys as _sys

from . import _geoenv as _geoenv

_PROJ_ENV_CHANGES = _geoenv.configure()


def _soften_console() -> None:
    """Konsol kod sayfası dar olduğunda çıktının çökmesini engeller.

    Türkçe Windows konsolu cp1254 kullanır ve içinde `ρ` (U+03C1) yoktur.
    Adım 7 tam da bu yüzden, bütün hesap bittikten SONRA, yalnızca sonucu
    yazdırmaya çalışırken UnicodeEncodeError ile düşüyordu — dakikalarca
    süren bir işin çıktısı tek bir karakter yüzünden kayboluyordu.

    Kodlamayı değiştirmiyoruz (mojibake üretirdi), yalnızca kodlanamayan
    karakterin konsolda `?` olmasına izin veriyoruz. Rapor dosyaları zaten
    ayrıca `encoding="utf-8"` ile yazılıyor; onlarda kayıp olmuyor.
    """
    for stream in (_sys.stdout, _sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass  # yeniden yönlendirilmiş akış: dokunma


_soften_console()

__version__ = "0.1.0"
