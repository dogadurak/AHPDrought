"""Eurostat bölgesel verim serisi — uzaktan algılama OLMAYAN etki ölçüsü.

## Neden gerekli

Adım 13-14'te risk haritasının mekânsal deseni iki uydu tabanlı etki ölçüsüyle
(NDVI, ET/PET) sınandı ve doğrulanmadı. Geriye kalan en makul açıklama, 30 m
ölçekte etkiyi fiziksel duyarlılıktan çok **parsel düzeyi yönetim kararlarının**
belirlediğiydi — hangi ürün, sulanıyor mu, kuyu erişimi var mı.

Bunu sınamanın yolu, yönetim kararlarının sonucunu da içeren bir ölçü kullanmak:
**verim**. TÜİK'in ilçe verisi makine okunur değil (site bir SPA, her yola aynı
HTML kabuğunu döndürüyor). Ancak Türkiye Eurostat'a NUTS-2 düzeyinde bölgesel
tarım istatistiği raporluyor ve Eurostat'ın açık REST API'si var.

## SONUÇ: BU KAYNAK BU İŞ İÇİN YETERSİZ (ölçüldü, belgelendi)

Modül çalışıyor ve veriyi indiriyor, ama indirilen veri araştırma sorusunu
cevaplayamıyor. Üç somut sebep — üçü de kod içindeki kalite denetimleriyle
yakalanıyor:

1. **Veri giriş hatası.** TR33 tahılında 2000-2004 için üretim ve alan
   BİREBİR AYNI sayı raporlanmış (ör. 2000: üretim 2250.9 bin ton, alan
   2250.9 bin ha). Bölünce verim tam 1.00 t/ha çıkıyor — gerçek değil,
   artefakt. Denetim olmasa beş uydurma yıl analize girerdi.
2. **Ana ürünlerde üretim yok.** Üzüm (W1000) ve zeytin (O1000) için yalnızca
   ALAN raporlanmış, üretim yok. Yani Gediz'in en önemli iki ürünü için verim
   hesaplanamıyor.
3. **Pamuk 2011'de başlıyor.** Havzanın gerçek kuraklıkları (2001, 2007, 2008)
   kapsam dışında kalıyor.

Geriye kullanılabilir olarak yalnızca 2011-2024 tahıl ve pamuk kalıyor; ikisi
de kuraklık yıllarını kaçırıyor ve TR33 tahılı ağırlıkla havza dışındaki
(Afyon/Kütahya/Uşak) yağmura bağlı alanlardan geliyor.

**Modül neden repoda kalıyor:** "verim verisi bulunamadı" iddiası, denenmiş ve
belgelenmiş olduğu için savunulabilir. Kalite denetimleri de yeniden
kullanılabilir — başka bir bölge ya da güncellenmiş bir sürüm denendiğinde
aynı tuzaklar otomatik yakalanır.

## Ne veriyor, ne vermiyor (tasarım gereği)

VERMİYOR: mekânsal ayrıntı. TR33 bölgesi Manisa + Afyonkarahisar + Kütahya +
Uşak'ı kapsar, havzadan çok daha geniştir. Bu veri **haritanın mekânsal
desenini hiçbir koşulda doğrulayamaz**; en iyi ihtimalle havza ölçeğinde
"kuraklık verim kaybına yol açıyor mu" sorusunu cevaplardı.

TÜİK'in ilçe verisi bunu çözerdi ama makine okunur değil: site bir SPA ve
her yola — anlamsız parametreler dahil — aynı 3.7 KB'lik HTML kabuğunu
döndürüyor. Statik dosya, indirme uç noktası ya da API yok.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from ..config import Config
from .common import interim_path

BASE = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
YIELD_FILE = "regional_crop_yield.csv"

# Gediz havzasının ana ürünleri (Eurostat ürün kodları)
CROPS = {
    "W1000": "uzum",
    "O1000": "zeytin",
    "I2300": "pamuk_lifi",
    "C0000": "tahil",
}
# DİKKAT: Türkiye, Eurostat'a hazır VERİM göstergesini (YLD_HUMD_EU_T_HA)
# raporlamıyor — TR33 için sıfır gözlem var. Ama üretim ve alan raporlanıyor,
# verim de zaten bunların oranıdır:
#
#     verim (t/ha) = hasat edilen üretim (bin ton) / hasat alanı (bin ha)
#
# Bu, hazır göstergeyi beklemek yerine elde olandan türetmek demek.
PRODUCTION = "HPRD_HUMD_EU_THS_T"   # hasat edilen üretim, bin ton
AREA = "AR_THS_HA"                  # alan, bin hektar
AREA_FALLBACK = "MAR_THS_HA"        # ana alan (bazı ürünlerde AR yok)

# Anomali için gereken en az yıl sayısı.
MIN_YEARS_FOR_ANOMALY = 10
# Artık sapması serinin kendi ölçeğinin bu kadarının altındaysa anomali
# tanımsız sayılır (sıfıra bölme koruması).
RESIDUAL_STD_FLOOR = 0.02


def fetch_regional_yield(
    config: Config,
    *,
    region: str = "TR33",
    overwrite: bool = False,
    timeout: int = 120,
) -> Path:
    """Eurostat'tan bölgesel yıllık verim serisini indirir ve CSV'ye yazar."""
    out = interim_path(config, YIELD_FILE)
    if out.exists() and not overwrite:
        existing = pd.read_csv(out, index_col=0)
        print(f"  [Eurostat verim] önbellekten: {out.name} "
              f"({len(existing)} yıl, {list(existing.columns)})")
        return out

    print(f"  [Eurostat verim] bölge {region}; verim = üretim / alan "
          f"({PRODUCTION} / {AREA})")
    response = requests.get(
        f"{BASE}/apro_cpshr",
        params={"format": "JSON", "geo": region, "lang": "EN"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()

    production = _to_frame(payload, CROPS, PRODUCTION)
    area = _to_frame(payload, CROPS, AREA)
    fallback = _to_frame(payload, CROPS, AREA_FALLBACK)

    # Bazı ürünlerde AR_THS_HA yok, MAR_THS_HA var — eksikleri onunla doldur.
    area = area.reindex(columns=production.columns)
    fallback = fallback.reindex(columns=production.columns, index=area.index)
    area = area.fillna(fallback)

    if production.empty or area.empty:
        raise RuntimeError(f"{region} için üretim/alan gözlemi yok")

    frame, dropped = _yield_with_quality_checks(production, area)
    if dropped:
        print(f"      KALİTE DENETİMİ: {len(dropped)} gözlem elendi")
        for reason, items in dropped.items():
            print(f"        {reason}: {items}")

    frame.to_csv(out)
    print(f"  [Eurostat verim] {len(frame)} yıl ({frame.index.min()}-{frame.index.max()})")
    for column in frame.columns:
        series = frame[column].dropna()
        if series.empty:
            continue
        print(f"      {column:<12} {series.min():5.2f} - {series.max():5.2f} t/ha "
              f"(ortalama {series.mean():.2f}, {len(series)} yıl)")
    return out


def _yield_with_quality_checks(
    production: pd.DataFrame, area: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, list]]:
    """Verimi hesaplar ve fiziksel olarak imkânsız değerleri eler.

    İki denetim:

    1. **üretim == alan** — Eurostat'ta TR33 tahılı 2000-2004 için ikisini de
       aynı sayı olarak raporlamış. Bölünce tam 1.00 çıkıyor; gerçek bir verim
       değil, veri giriş hatası. Tam eşitlik tesadüf olamaz.
    2. **fiziksel aralık** — tahıl için 0.5-8 t/ha, pamuk lifi için 0.3-3 t/ha
       dışındaki değerler kabul edilmez. Pamuk lifinde 5.33 t/ha görüldü;
       dünya rekoru bunun yarısı kadardır, yani alan/üretim tanımları
       eşleşmiyor demektir.
    """
    limits = {"tahil": (0.5, 8.0), "pamuk_lifi": (0.3, 3.0),
              "uzum": (2.0, 40.0), "zeytin": (0.5, 20.0)}
    dropped: dict[str, list] = {}

    identical = (production == area) & production.notna()
    if identical.any().any():
        dropped["üretim ile alan birebir aynı (veri giriş hatası)"] = [
            f"{c}:{y}" for c in identical.columns for y in identical.index[identical[c]]
        ]

    result = production / area.replace(0, pd.NA)
    result = result.mask(identical)

    for column in result.columns:
        low, high = limits.get(column, (0.0, float("inf")))
        bad = result[column].notna() & ((result[column] < low) | (result[column] > high))
        if bad.any():
            dropped.setdefault(f"{column}: fiziksel aralık dışı ({low}-{high} t/ha)", []).extend(
                f"{y}={result.loc[y, column]:.2f}" for y in result.index[bad]
            )
            result.loc[bad, column] = pd.NA

    return result.dropna(how="all").dropna(axis=1, how="all"), dropped


def _to_frame(payload: dict, crops: dict[str, str], indicator: str) -> pd.DataFrame:
    """Eurostat JSON-stat yanıtını yıl x ürün tablosuna çevirir.

    JSON-stat, gözlemleri boyutların KARTEZYEN çarpımı üzerinde tek bir düz
    indeksle saklar; indeksi elle çözmek gerekir.
    """
    dimension = payload["dimension"]
    order = payload.get("id") or list(dimension)
    sizes = payload.get("size") or [len(dimension[d]["category"]["index"]) for d in order]

    indexes = {d: dimension[d]["category"]["index"] for d in order}
    reverse = {d: {v: k for k, v in idx.items()} for d, idx in indexes.items()}

    # Düz indeksten çok boyutlu koordinata: satır-major (son boyut en hızlı)
    strides = [1] * len(order)
    for i in range(len(order) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    records: dict[tuple[int, str], float] = {}
    for flat, value in payload["value"].items():
        remainder = int(flat)
        coords = {}
        for dim, stride in zip(order, strides):
            coords[dim] = reverse[dim][remainder // stride]
            remainder %= stride

        if coords.get("strucpro") != indicator:
            continue
        crop = coords.get("crops")
        if crop not in crops:
            continue
        records[(int(coords["time"]), crops[crop])] = float(value)

    if not records:
        return pd.DataFrame()

    frame = pd.DataFrame(
        [{"year": y, "crop": c, "yield": v} for (y, c), v in records.items()]
    ).pivot(index="year", columns="crop", values="yield")
    frame.index.name = "year"
    return frame.sort_index()


def load_regional_yield(config: Config) -> pd.DataFrame:
    path = interim_path(config, YIELD_FILE)
    if not path.exists():
        raise FileNotFoundError(
            f"{YIELD_FILE} yok. Önce `python -m scripts.step15_yield --fetch` çalıştırın."
        )
    return pd.read_csv(path, index_col=0)


def yield_anomaly(frame: pd.DataFrame, *, detrend: bool = True) -> pd.DataFrame:
    """Verim anomalisi (z-skoru).

    `detrend=True` ise önce doğrusal eğilim çıkarılır. Gerekçe: tarımsal verim
    çeşit ıslahı, gübreleme ve sulama yatırımıyla on yıllar boyunca ARTAR.
    Bu eğilim çıkarılmazsa 2000'lerin başındaki düşük verimler "kuraklık" diye,
    2020'lerin yüksek verimleri "bolluk" diye okunur — yani teknolojik gelişme
    iklim sinyaliyle karıştırılır.
    """
    import numpy as np

    result = {}
    for column in frame.columns:
        series = frame[column].dropna()
        if len(series) < MIN_YEARS_FOR_ANOMALY:
            continue

        values = series.to_numpy(dtype=float)
        scale = float(np.nanstd(values, ddof=1))

        if detrend:
            years = series.index.to_numpy(dtype=float)
            slope, intercept = np.polyfit(years, values, 1)
            values = values - (slope * years + intercept)

        residual_std = float(np.nanstd(values, ddof=1))
        # Artık sapması, serinin kendi ölçeğine göre ihmal edilebilirse z-skoru
        # tanımsızdır: sıfıra bölmeye yaklaşır ve kayan nokta gürültüsünü
        # ±2 sigma'lık "anomali" gibi gösterir. (monitor.py'deki MIN_BASELINE_STD
        # ile aynı sınıf hata; orada da ölçülmüştü.)
        if residual_std < RESIDUAL_STD_FLOOR * max(scale, 1e-12):
            print(f"      {column}: eğilim çıkarıldıktan sonra artık kalmadı "
                  f"(std {residual_std:.2e}) — anomali tanımsız, atlandı")
            continue

        result[column] = pd.Series((values - values.mean()) / residual_std, index=series.index)
    return pd.DataFrame(result)
