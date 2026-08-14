"""Uzun aylık iklim serisi — SPI ve tahmin modülünün girdisi (Adım 10).

Kaynak: TerraClimate (Abatzoglou ve ark. 2018), Idaho Üniversitesi THREDDS
sunucusu üzerinden **OPeNDAP** ile. Aylık, ~4 km, 1958'den bugüne.

## Neden OPeNDAP

Aynı veri Planetary Computer'da zarr olarak da var ama chunk yapısı
(12, 1024, 1024) float64 = **101 MB/chunk**. Bu AOI 12x24 piksel ve tek bir
chunk'ın içinde kalıyor; 64 yıllık seriyi çekmek için 64 chunk, yani ~6.4 GB
transfer gerekiyordu — 768 sayı almak için.

OPeNDAP sunucu tarafında dilimler: aynı 768 sayı için birkaç KB iner.
Ölçülen maliyet yıl başına ~18 saniye (çoğu, global grid metadatasının
pazarlığı).

## Neden havza ortalaması

Tahmin modülü havza ölçeğinde çalışır. TerraClimate 4 km çözünürlükte ve AOI'yi
12x24 hücreyle kaplıyor; bu çözünürlükte piksel bazlı 3 ay sonrası tahmini
üretmek, veride olmayan bir kesinlik iddiası olurdu. Mekânsal risk haritası
zaten 30 m'de duruyor — tahmin ona **zaman boyutu** ekler, mekânsal detay değil.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from ..config import Config
from .common import interim_path

THREDDS = "https://thredds.northwestknowledge.net/thredds/dodsC/TERRACLIMATE_ALL/data"
SERIES_FILE = "basin_monthly_climate.csv"

# Dosya adındaki simge ile sütun adı her zaman aynı değil: PDSI dosyaları
# BÜYÜK harflidir (`TerraClimate_PDSI_1958.nc`), yağış küçük (`..._ppt_...`).
# Sunucuda tahminle isim üretmek yerine eşleme açıkça tutulur.
FILE_TOKEN = {"ppt": "ppt", "pdsi": "PDSI", "pet": "pet", "soil": "soil", "tmax": "tmax"}


def fetch_basin_climate_series(
    config: Config,
    *,
    variables: tuple[str, ...] = ("ppt", "pdsi"),
    start_year: int = 1958,
    end_year: int | None = None,
    overwrite: bool = False,
) -> Path:
    """AOI ortalaması aylık iklim serisini CSV olarak indirir ve önbelleğe alır.

    Args:
        variables: TerraClimate değişken adları.
            `ppt`  — aylık toplam yağış (mm), SPI'ın girdisi.
            `pdsi` — Palmer Kuraklık Şiddet İndeksi. Kriter değil; kendi SPI
                     hesabımızı BAĞIMSIZ olarak sınamak için (farklı yöntem,
                     farklı formülasyon, aynı olguyu ölçüyor).
        end_year: None ise içinde bulunulan yıla kadar denenir; sunucuda
            olmayan yıllar sessizce atlanır.
    """
    import xarray as xr

    out = interim_path(config, SERIES_FILE)
    if out.exists() and not overwrite:
        existing = pd.read_csv(out, index_col=0, parse_dates=True)
        print(f"  [iklim serisi] önbellekten: {out.name} "
              f"({len(existing)} ay, {existing.index[0]:%Y-%m} - {existing.index[-1]:%Y-%m})")
        return out

    min_lon, min_lat, max_lon, max_lat = config["aoi"]["bbox_wgs84"]
    end_year = end_year or pd.Timestamp.today().year

    print(f"  [iklim serisi] TerraClimate OPeNDAP, {start_year}-{end_year}, "
          f"değişkenler: {', '.join(variables)}")
    print("      (yıl başına ~18 sn; gerçek veri transferi birkaç KB — sunucu tarafında dilimlenir)")

    columns: dict[str, pd.Series] = {}
    failures: dict[str, str] = {}

    for variable in variables:
        try:
            columns[variable] = _fetch_variable(
                xr, variable, start_year, end_year, (min_lon, min_lat, max_lon, max_lat)
            )
        except RuntimeError as exc:
            failures[variable] = str(exc)
            print(f"      {variable}: ALINAMADI — {exc}")

    if not columns:
        raise RuntimeError(f"Hiçbir değişken indirilemedi: {failures}")

    # Başarılı değişkenler her hâlükârda yazılır. Bir değişkenin başarısızlığı
    # yüzünden saatlerce süren indirmeyi çöpe atmak kabul edilemez.
    if failures:
        print(
            f"      UYARI: {sorted(failures)} alınamadı, {sorted(columns)} yazılıyor. "
            "Eksik değişken için komutu tekrar çalıştırın."
        )

    frame = pd.DataFrame(columns).sort_index()
    frame.index.name = "time"

    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out)

    span = f"{frame.index[0]:%Y-%m} - {frame.index[-1]:%Y-%m}"
    print(f"  [iklim serisi] {len(frame)} ay ({span}), {frame.index.year.nunique()} yıl")
    for name in frame.columns:
        series = frame[name].dropna()
        print(f"      {name:5} {series.min():8.2f} .. {series.max():8.2f}  (ortalama {series.mean():7.2f})")
    print(f"  [iklim serisi] yazıldı: {out.name} ({out.stat().st_size / 1024:.0f} KB)")
    return out


def _fetch_variable(
    xr,
    variable: str,
    start_year: int,
    end_year: int,
    bbox: tuple[float, float, float, float],
    *,
    attempts: int = 3,
) -> pd.Series:
    """Tek bir değişkenin yıllık dosyalarını gezip havza ortalamasını toplar.

    Geçici ağ hatası ile "sunucuda böyle bir yıl yok" farklı ele alınır:
    ilki tekrar denenir, ikincisi serinin sonu sayılır. Bu ayrım olmadan tek
    bir zaman aşımı, 60+ yıllık bir indirmeyi ortasından kesebiliyordu.
    """
    min_lon, min_lat, max_lon, max_lat = bbox
    token = FILE_TOKEN.get(variable, variable)
    values: list[pd.Series] = []
    current_year = pd.Timestamp.today().year

    for year in range(start_year, end_year + 1):
        url = f"{THREDDS}/TerraClimate_{token}_{year}.nc"
        series = None
        last_error = None

        for attempt in range(1, attempts + 1):
            try:
                with xr.open_dataset(url, decode_timedelta=False) as ds:
                    name = variable if variable in ds else token
                    if name not in ds:
                        name = next(iter(ds.data_vars))
                    # TerraClimate enlemi AZALAN sırada: slice(kuzey, güney)
                    window = ds[name].sel(
                        lon=slice(min_lon, max_lon), lat=slice(max_lat, min_lat)
                    )
                    basin = window.mean(dim=["lat", "lon"]).compute()
                    series = pd.Series(basin.values, index=pd.to_datetime(basin.time.values))
                break
            except Exception as exc:
                last_error = exc
                if attempt < attempts:
                    continue

        if series is not None:
            values.append(series)
            if year % 10 == 0:
                print(f"      {variable}: {year} tamam")
            continue

        # Henüz yayımlanmamış yıllar beklenen bir durumdur, hata değil.
        if year >= current_year - 1:
            print(f"      {variable}: {year} henüz yayımlanmamış, seri {year - 1}'de bitiyor")
            break
        print(f"      {variable} {year}: {attempts} denemede alınamadı "
              f"({type(last_error).__name__}), atlandı")

    if not values:
        raise RuntimeError(f"hiç yıl indirilemedi (dosya adı simgesi: {token})")
    return pd.concat(values).sort_index()


def load_basin_climate_series(config: Config) -> pd.DataFrame:
    """Önbellekteki iklim serisini okur."""
    path = interim_path(config, SERIES_FILE)
    if not path.exists():
        raise FileNotFoundError(
            f"{SERIES_FILE} bulunamadı. Önce "
            "`python -m scripts.step10_forecast --fetch` çalıştırın."
        )
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index.name = "time"
    return frame


def annual_summary(frame: pd.DataFrame, column: str = "ppt") -> pd.DataFrame:
    """Yıllık toplam yağış ve sıralaması — kurak yılları görmek için."""
    annual = frame[column].resample("YE").sum()
    return pd.DataFrame(
        {
            "toplam_mm": annual.round(1),
            "normale_oran": (annual / annual.mean()).round(3),
            "siralama": annual.rank(ascending=True).astype(int),
        }
    )
