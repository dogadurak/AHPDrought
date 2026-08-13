"""Su kaynağına Öklid mesafesi raster'ı (Adım 3).

OSM'den gelen akarsu çizgileri ve göl/rezervuar poligonları ortak grid'e
rasterleştirilir, ardından `scipy.ndimage.distance_transform_edt` ile her
piksele en yakın su pikseline olan mesafe (metre) hesaplanır.

İki incelik:
  1. `sampling=(res, res)` verilmezse mesafe PİKSEL cinsinden çıkar; metre
     sanıp kullanmak 30 kat hataya yol açar.
  2. Akarsu çizgileri 30 m hücrede tel kadar incedir; `all_touched=True`
     olmadan rasterleştirmede çizginin büyük kısmı düşer ve mesafe haritası
     kopuk çıkar.
"""

from __future__ import annotations

import numpy as np

from ..grid import TargetGrid


def rasterize_water(gdf, grid: TargetGrid) -> np.ndarray:
    """Su geometrilerini grid üzerinde boolean maskeye çevirir."""
    from rasterio.features import rasterize

    if gdf.crs is None:
        raise ValueError("Su katmanının CRS'i tanımsız")
    if str(gdf.crs) != str(grid.crs):
        gdf = gdf.to_crs(grid.crs)

    geometries = [geom for geom in gdf.geometry if geom is not None and not geom.is_empty]
    if not geometries:
        raise ValueError("Rasterleştirilecek su geometrisi yok")

    mask = rasterize(
        ((geom, 1) for geom in geometries),
        out_shape=grid.shape,
        transform=grid.transform,
        fill=0,
        # İnce akarsu çizgilerinin kaybolmaması için dokunulan her hücre işaretlenir.
        all_touched=True,
        dtype="uint8",
    )
    return mask.astype(bool)


def distance_to_water(water_mask: np.ndarray, grid: TargetGrid) -> np.ndarray:
    """Her piksel için en yakın su pikseline olan mesafeyi metre olarak verir.

    Su piksellerinin kendisi 0 m alır.
    """
    from scipy.ndimage import distance_transform_edt

    if water_mask.shape != grid.shape:
        raise ValueError(f"Maske şekli {water_mask.shape}, grid {grid.shape} ile uyuşmuyor")
    if not water_mask.any():
        raise ValueError("Su maskesi tamamen boş — mesafe tanımsız")

    # distance_transform_edt SIFIR olmayan hücrelerden sıfıra olan mesafeyi
    # ölçer; bu yüzden maskeyi tersleyip veriyoruz.
    distance = distance_transform_edt(
        ~water_mask,
        sampling=(grid.resolution, grid.resolution),  # piksel değil METRE
    )
    return distance.astype("float32")


def build_distance_raster(gdf, grid: TargetGrid) -> np.ndarray:
    """Vektörden mesafe raster'ına tek adımda."""
    mask = rasterize_water(gdf, grid)
    coverage = 100 * mask.mean()
    distance = distance_to_water(mask, grid)
    print(
        f"      su pikselleri %{coverage:.2f}, mesafe 0 - {distance.max():,.0f} m "
        f"(ortalama {distance.mean():,.0f} m)"
    )
    return distance
