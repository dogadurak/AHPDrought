"""DEM'den eğim ve bakı türetimi (Adım 3).

Yöntem: Horn (1981) 3x3 operatörü — GDAL, ArcGIS ve QGIS'in varsayılanı.
Basit merkezi farka göre gürültüye daha dayanıklıdır.

3x3 pencere (satır indeksi güneye doğru artar, yani a-b-c KUZEY sırasıdır):

    a b c        KB  K  KD
    d e f   =     B  .   D
    g h i        GB  G  GD

    dz/dx_dogu   = ((c + 2f + i) - (a + 2d + g)) / (8 * hucre)
    dz/dy_kuzey  = ((a + 2b + c) - (g + 2h + i)) / (8 * hucre)

Bakı, en dik İNİŞ yönünün pusula açısıdır (kuzeyden saat yönünde):

    bakı = atan2(-dz/dx_dogu, -dz/dy_kuzey)  (mod 360)

Bakı 0-360 arası DAİRESEL bir değişkendir ve doğrudan normalize edilemez
(359° ile 1° komşudur ama min-max ölçeğinin iki ucuna düşer). Bu yüzden
güneyliliğe (southness) indirgenir:

    southness = (1 - cos(bakı)) / 2     kuzey -> 0.0,  güney -> 1.0

Eğimin ~0 olduğu düz alanlarda bakı matematiksel olarak tanımsızdır; bu
piksellere yanlı bir yön atamak yerine nötr değer (config'te `flat_fill`)
verilir.
"""

from __future__ import annotations

import numpy as np


def horn_gradients(dem: np.ndarray, cell_size: float) -> tuple[np.ndarray, np.ndarray]:
    """Horn 3x3 operatörüyle doğu ve kuzey yönlü eğimleri hesaplar.

    Kenar pikselleri için dizi kenar değeriyle doldurulur (`edge` modu), böylece
    sınırda yapay uçurum oluşmaz.

    Returns:
        (dz/dx_dogu, dz/dy_kuzey) — ikisi de boyutsuz eğim (yükseklik/mesafe).
    """
    if cell_size <= 0:
        raise ValueError(f"Hücre boyutu pozitif olmalı: {cell_size}")
    if dem.ndim != 2:
        raise ValueError(f"DEM 2 boyutlu olmalı, şekil: {dem.shape}")

    p = np.pad(dem.astype("float64"), 1, mode="edge")

    a, b, c = p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:]   # kuzey satırı
    d, f = p[1:-1, :-2], p[1:-1, 2:]                   # orta satır (merkez hariç)
    g, h, i = p[2:, :-2], p[2:, 1:-1], p[2:, 2:]       # güney satırı

    dz_dx_east = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * cell_size)
    dz_dy_north = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * cell_size)

    return dz_dx_east, dz_dy_north


def slope_degrees(dem: np.ndarray, cell_size: float) -> np.ndarray:
    """Eğimi derece cinsinden döndürür (0 = düz, 90 = dikey)."""
    dz_dx, dz_dy = horn_gradients(dem, cell_size)
    return np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype("float32")


def aspect_degrees(dem: np.ndarray, cell_size: float) -> np.ndarray:
    """Bakıyı derece cinsinden döndürür (0 = kuzey, 90 = doğu, saat yönünde).

    En dik iniş yönüdür. Tam düz alanlarda atan2(0, 0) = 0 döner; bu değerin
    anlamı yoktur ve `southness()` içinde eğim eşiğiyle ayıklanır.
    """
    dz_dx, dz_dy = horn_gradients(dem, cell_size)
    aspect = np.degrees(np.arctan2(-dz_dx, -dz_dy))
    return np.mod(aspect, 360.0).astype("float32")


def southness(
    aspect_deg: np.ndarray,
    slope_deg: np.ndarray,
    *,
    flat_slope_threshold_deg: float = 1.0,
    flat_fill: float = 0.5,
) -> np.ndarray:
    """Dairesel bakıyı 0-1 aralığında güneylilik skoruna çevirir.

    kuzey (0°) -> 0.0,  doğu/batı (90°/270°) -> 0.5,  güney (180°) -> 1.0

    Args:
        flat_slope_threshold_deg: Bu eğimin altındaki pikseller "düz" sayılır ve
            bakıları tanımsız kabul edilir.
        flat_fill: Düz piksellere atanacak nötr değer.
    """
    if not 0.0 <= flat_fill <= 1.0:
        raise ValueError(f"flat_fill 0-1 aralığında olmalı: {flat_fill}")
    if aspect_deg.shape != slope_deg.shape:
        raise ValueError(f"Şekiller uyuşmuyor: {aspect_deg.shape} vs {slope_deg.shape}")

    score = (1.0 - np.cos(np.radians(aspect_deg.astype("float64")))) / 2.0
    score = np.where(slope_deg < flat_slope_threshold_deg, flat_fill, score)
    return np.clip(score, 0.0, 1.0).astype("float32")
