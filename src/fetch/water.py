"""OSM su ve sulama altyapısı vektörleri (Adım 2).

Kaynak: OpenStreetMap (Overpass API, `osmnx` üzerinden).

İki AYRI katman üretilir ve bilinçli olarak birleştirilmez:

  water.gpkg       akarsu, göl, rezervuar — DOĞAL yüzey suyu
  irrigation.gpkg  kanal, ark, drenaj, pompa — MÜHENDİSLİK ESERİ su iletimi

Gerekçe: bunlar farklı süreçlerdir. Doğal suya yakınlık taban suyu ve riparyen
nemi temsil eder; sulama şebekesine yakınlık ise kurak dönemde suyu telafi
edebilme imkânını. Gediz ovasında ikisi mekânsal olarak da ayrışır — kanal ağı
ovaya yayılırken akarsular vadi tabanında toplanır. Tek katmanda birleştirmek
iki farklı süreci tek AHP ağırlığına bindirirdi.

Etiket grupları AYRI AYRI sorgulanır: osmnx, sorgu hiç sonuç döndürmediğinde
`InsufficientResponseError` fırlatır; tek birleşik sorguda AOI'de karşılığı
olmayan bir etiket tüm indirmeyi düşürürdü.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from ..config import Config
from ..grid import TargetGrid
from .common import interim_path, skip_if_cached


def fetch_water_features(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """Doğal yüzey suyu geometrilerini GeoPackage olarak yazar."""
    return _fetch_osm_layer(
        config, grid, source_key="water", filename="water.gpkg", label="OSM su",
        overwrite=overwrite,
    )


def fetch_irrigation_features(config: Config, grid: TargetGrid, *, overwrite: bool = False) -> Path:
    """Sulama iletim altyapısı geometrilerini GeoPackage olarak yazar."""
    return _fetch_osm_layer(
        config, grid, source_key="irrigation", filename="irrigation.gpkg",
        label="OSM sulama", overwrite=overwrite,
    )


def _fetch_osm_layer(
    config: Config,
    grid: TargetGrid,
    *,
    source_key: str,
    filename: str,
    label: str,
    overwrite: bool,
) -> Path:
    out = interim_path(config, filename)
    if skip_if_cached(out, overwrite, label):
        return out

    cfg = config["data_sources"][source_key]
    bbox = tuple(config["aoi"]["bbox_wgs84"])

    frames: list = []
    failed: list[str] = []

    for tags in cfg["tag_groups"]:
        tag_label = ", ".join(f"{k}={v}" for k, v in tags.items())
        try:
            frame = _query(tags, bbox)
        except OSMQueryError as exc:
            failed.append(tag_label)
            print(f"      {tag_label:<52} SORGU BAŞARISIZ: {exc}")
            continue

        if frame is None or frame.empty:
            print(f"      {tag_label:<52} sonuç yok (atlandı)")
            continue

        before = len(frame)
        frame = _apply_exclusions(frame, cfg.get("exclude_tag_values") or {})
        removed = before - len(frame)
        suffix = f"  ({removed} tanesi exclude_tag_values ile ayıklandı)" if removed else ""

        if frame.empty:
            print(f"      {tag_label:<52} tümü ayıklandı{suffix}")
            continue
        print(
            f"      {tag_label:<52} {len(frame):>4} özellik "
            f"{frame.geom_type.value_counts().to_dict()}{suffix}"
        )
        frames.append(frame)

    # "Sonuç yok" ile "sorgu başarısız" farklı şeylerdir. İlki beklenen bir
    # durumdur (AOI'de o etiket yoktur). İkincisi katmanı EKSİK bırakır ve
    # eksik bir ağdan hesaplanan mesafe raster'ı sessizce yanlış olur — bu
    # yüzden kısmi sonuçla devam edilmez.
    if failed:
        raise RuntimeError(
            f"{len(failed)} etiket grubu indirilemedi: {failed}. "
            f"Kısmi bir {source_key} ağından hesaplanan mesafe raster'ı yanlış olurdu. "
            "Başarılı gruplar önbellekte kaldı; komutu tekrar çalıştırmak yalnızca "
            "eksik grupları indirir."
        )

    if not frames:
        raise RuntimeError(
            f"OSM'de AOI için hiç {source_key} özelliği yok. "
            f"data_sources.{source_key}.tag_groups ayarını kontrol edin."
        )

    merged = gpd.GeoDataFrame(
        pd.concat([f[["geometry", "source_tags"]] for f in frames], ignore_index=True),
        crs="EPSG:4326",
    )

    # Mesafe hesabı metrik olmalı: hedef CRS'e al, grid kapsamına kır.
    merged = merged.to_crs(grid.crs)
    merged = merged[merged.is_valid & ~merged.is_empty]
    merged = gpd.clip(merged, box(*grid.bounds))
    merged = merged[~merged.is_empty]

    if merged.empty:
        raise RuntimeError(f"{source_key} geometrileri grid kapsamıyla kesişmiyor")

    lines = merged[merged.geom_type.isin(["LineString", "MultiLineString"])]
    polygons = merged[merged.geom_type.isin(["Polygon", "MultiPolygon"])]
    print(
        f"  [{label}] {len(merged)} geometri, {lines.length.sum() / 1000:,.0f} km hat, "
        f"{polygons.area.sum() / 1e6:,.1f} km² alan"
    )

    merged.to_file(out, driver="GPKG", layer=source_key)
    print(f"  [{label}] yazıldı: {out.name}")
    return out


def _apply_exclusions(frame: gpd.GeoDataFrame, exclusions: dict) -> gpd.GeoDataFrame:
    """Belirtilen etiket değerlerine sahip özellikleri ayıklar.

    Bir katmana ait olmayan alt tipleri (ör. doğal su katmanındaki sulama
    kanalları) sorgu sonrasında elemek için. Sorguyu daraltmakla aynı sonucu
    verir ama önbellekteki yanıtı yeniden kullanır.
    """
    for column, values in exclusions.items():
        if column not in frame.columns:
            continue
        frame = frame[~frame[column].isin(values)]
    return frame


class OSMQueryError(RuntimeError):
    """Overpass sorgusu teknik nedenle başarısız oldu (sonuçsuz kalmaktan farklı)."""


# Overpass'ın ana sunucusu sık sık kota/zaman aşımı verir. Aynı veriyi sunan
# aynalar denenir; osmnx başarılı yanıtları diske önbelleklediği için tekrar
# çalıştırmalar ücretsizdir.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.jp/api/interpreter",
)


def _query(tags: dict, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame | None:
    """Tek bir etiket grubunu sorgular.

    Returns:
        Sonuç varsa GeoDataFrame, AOI'de o etiket hiç yoksa None.

    Raises:
        OSMQueryError: Tüm Overpass aynaları teknik nedenle başarısız olduysa.
    """
    import osmnx as ox
    from osmnx._errors import InsufficientResponseError

    errors = []
    for endpoint in OVERPASS_ENDPOINTS:
        ox.settings.overpass_url = endpoint.rsplit("/api/interpreter", 1)[0] + "/api"
        try:
            frame = ox.features_from_bbox(bbox, tags)
        except InsufficientResponseError:
            return None  # sorgu çalıştı, AOI'de bu etiket yok
        except Exception as exc:
            errors.append(f"{endpoint.split('/')[2]}: {type(exc).__name__}")
            continue

        frame = frame[frame.geometry.notna()].copy()
        frame["source_tags"] = ", ".join(f"{k}={v}" for k, v in tags.items())
        return frame.reset_index(drop=True)

    raise OSMQueryError(f"tüm Overpass aynaları başarısız ({'; '.join(errors)})")
