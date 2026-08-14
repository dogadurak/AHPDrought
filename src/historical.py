"""Adım 13 — Risk haritasının GERÇEK kuraklıklarda sınanması.

## Neden gerekli

Adım 11'deki sınama "KARAR VERİLEMEZ" ile bitti: Sentinel-2 döneminde
(2017-2025) yalnızca bir kurak yıl vardı ve o da orta şiddetteydi. Oysa 68
yıllık yağış kaydında havzanın gerçek kuraklıkları uydu öncesine düşüyor:

    1989-01 – 1991-02   26 ay   en düşük SPI-12 = -2.63
    2000-11 – 2001-11   13 ay   en düşük SPI-12 = -2.56
    1991-12 – 1993-01   14 ay   en düşük SPI-12 = -2.29
    2007-01 – 2007-11   11 ay   en düşük SPI-12 = -2.61

Landsat 5 (1984-2011, 30 m) bu dönemi kapsıyor ve projenin grid'iyle aynı
çözünürlükte. Bu, haritayı **ağır stres altında** sınamanın tek yolu.

## Bu sınamanın kendi sınırlılığı (raporda öne çıkarılır)

Risk haritası BUGÜNKÜ sulama ağı ve arazi örtüsüyle kuruldu. 1990'ı sınarken
"bu mekânsal desen 35 yılda değişmedi" varsayımı yapılıyor. Bu varsayım:

  - topoğrafya (eğim, bakı) ve toprak için    -> güvenli
  - yağış ve sıcaklık deseni için             -> büyük ölçüde güvenli
  - sulama ağı ve arazi örtüsü için           -> TARTIŞMALI

Gediz'de sulu tarım 1990'dan bu yana genişledi. Dolayısıyla tarihsel sınama,
haritanın **bugünkü** hâlinin **geçmişteki** kuraklıkta ne kadar iyi çalışacağını
ölçer — geçmişte gerçekten geçerli olan bir haritayı değil. Sonuç bu çerçevede
okunmalıdır.

## Dönemler karıştırılmaz

Landsat NDVI'ı Sentinel-2 NDVI'ından sistematik olarak farklıdır (sensör +
arazi kullanımı değişimi). Bu yüzden anomali **Landsat döneminin kendi
içinde**, kendi taban çizgisiyle hesaplanır.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .fetch.common import interim_path
from .grid import TargetGrid, read_grid_aligned

MIN_BASELINE_YEARS = 10


def available_years(config: Config) -> list[int]:
    """Üretilmiş Landsat yıllık kompozitleri."""
    directory = interim_path(config, "landsat_ndvi", "x").parent
    years = []
    for path in sorted(directory.glob("ndvi_*.tif")):
        try:
            years.append(int(path.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return years


def _layer(config: Config, grid: TargetGrid, year: int) -> np.ndarray:
    path = interim_path(config, "landsat_ndvi", f"ndvi_{year}.tif")
    array = read_grid_aligned(path, grid).astype("float32")
    return np.where(array == np.float32(config.nodata), np.nan, array)


def landsat_anomaly(
    config: Config,
    grid: TargetGrid,
    year: int,
    *,
    years: list[int] | None = None,
    standardize: bool = False,
) -> np.ndarray:
    """Bir yılın, Landsat döneminin geri kalanına göre NDVI anomalisi.

    Taban çizgisi hedef yılı DIŞLAR (leave-one-out) ve yalnızca Landsat
    yıllarından oluşur — Sentinel dönemiyle karıştırılmaz.
    """
    years = years or available_years(config)
    baseline_years = [y for y in years if y != year]
    if len(baseline_years) < MIN_BASELINE_YEARS:
        raise ValueError(
            f"Taban çizgisi {len(baseline_years)} yıl — en az {MIN_BASELINE_YEARS} gerekir"
        )

    target = _layer(config, grid, year)
    baseline = np.stack([_layer(config, grid, y) for y in baseline_years])
    mean = np.nanmean(baseline, axis=0)
    difference = target - mean

    if not standardize:
        return difference.astype("float32")

    std = np.nanstd(baseline, axis=0, ddof=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(std > 0.01, difference / std, np.nan).astype("float32")


def severity_index(spi12: pd.Series, years: list[int], months=(7, 8, 9)) -> dict[int, float]:
    """Her yıl için kurak dönem SPI-12 ortalaması — kuraklık şiddeti ölçütü.

    SPI-12 kullanılır çünkü tarımsal etki, o yazki yağıştan değil, önceki 12
    ayda biriken açıktan doğar. Yaz aylarında okunması, mahsulün gerçekten su
    talep ettiği anı temsil eder.
    """
    selected = spi12[spi12.index.month.isin(months)]
    by_year = selected.groupby(selected.index.year).mean()
    return {y: float(by_year.get(y, np.nan)) for y in years}


def historical_test(
    config: Config,
    grid: TargetGrid,
    risk_index: np.ndarray,
    risk_classes: np.ndarray,
    spi12: pd.Series,
    *,
    dry_threshold: float = -1.0,
    landcover_code: int | None = 40,
) -> dict:
    """Landsat döneminde risk–etki ilişkisini kurak ve normal yıllarda ölçer."""
    from .monitor import ANOMALY_CLASSES  # noqa: F401  (eşik uyumu için)
    from .validate import rank_correlation

    years = available_years(config)
    if len(years) < MIN_BASELINE_YEARS + 1:
        raise RuntimeError(f"Yalnızca {len(years)} Landsat yılı var")

    severity = severity_index(spi12, years)
    mask = None
    if landcover_code is not None:
        codes = read_grid_aligned(interim_path(config, "landcover.tif"), grid)
        mask = codes == landcover_code

    rows = []
    for year in years:
        anomaly = landsat_anomaly(config, grid, year, years=years)
        if mask is not None:
            anomaly = np.where(mask, anomaly, np.nan).astype("float32")

        spi_value = severity[year]
        is_dry = bool(np.isfinite(spi_value) and spi_value <= dry_threshold)
        by_class = []
        for code in range(1, config["classification"]["n_classes"] + 1):
            selection = (risk_classes == code) & np.isfinite(anomaly)
            if selection.sum():
                by_class.append((code, float(np.nanmean(anomaly[selection])), int(selection.sum())))

        rows.append(
            {
                "year": year,
                "spi12": spi_value,
                "is_dry": is_dry,
                "mean_anomaly": float(np.nanmean(anomaly)),
                "rho": rank_correlation(risk_index, anomaly),
                "by_class": by_class,
                "monotone": all(by_class[i][1] >= by_class[i + 1][1] for i in range(len(by_class) - 1)),
            }
        )
        print(f"      {year}: SPI-12 {spi_value:+.2f} "
              f"({'KURAK' if is_dry else 'normal'})  ρ = {rows[-1]['rho']:+.4f}")

    dry = [r for r in rows if r["is_dry"]]
    normal = [r for r in rows if not r["is_dry"]]
    return {
        "rows": rows,
        "dry": dry,
        "normal": normal,
        "dry_rho": float(np.mean([r["rho"] for r in dry])) if dry else float("nan"),
        "normal_rho": float(np.mean([r["rho"] for r in normal])) if normal else float("nan"),
        "threshold": dry_threshold,
        "landcover_code": landcover_code,
    }


def pooled_by_class(result: dict, *, dry_only: bool = True) -> list[tuple[int, float]]:
    """Seçili yılların sınıf ortalamalarını piksel sayısıyla ağırlıklı birleştirir."""
    selected = result["dry"] if dry_only else result["rows"]
    totals: dict[int, float] = {}
    weights: dict[int, int] = {}
    for row in selected:
        for code, mean_value, count in row["by_class"]:
            totals[code] = totals.get(code, 0.0) + mean_value * count
            weights[code] = weights.get(code, 0) + count
    return [(code, totals[code] / weights[code]) for code in sorted(totals)]


def summarize(config: Config, result: dict) -> str:
    """Sonucu okunur tabloya çevirir ve hüküm verir."""
    from .operational import MIN_DRY_YEARS, MIN_EFFECT_SIZE

    labels = config["classification"]["labels"]
    lines = [
        f"{'Yıl':<7}{'SPI-12':>9}{'durum':>9}{'ort. anomali':>15}{'risk-anomali ρ':>17}{'monoton':>10}",
        "-" * 67,
    ]
    for row in result["rows"]:
        lines.append(
            f"{row['year']:<7}{row['spi12']:>9.2f}{'KURAK' if row['is_dry'] else 'normal':>9}"
            f"{row['mean_anomaly']:>15.4f}{row['rho']:>17.4f}"
            f"{'evet' if row['monotone'] else 'hayır':>10}"
        )
    lines.append("-" * 67)

    dry, normal = result["dry"], result["normal"]
    lines += [
        f"Kurak yıllar  (n={len(dry)}): ortalama ρ = {result['dry_rho']:+.4f}"
        f"   [{', '.join(str(r['year']) for r in dry)}]",
        f"Normal yıllar (n={len(normal)}): ortalama ρ = {result['normal_rho']:+.4f}",
        f"Fark: {result['normal_rho'] - result['dry_rho']:+.4f}"
        "  (pozitif = kurak yıllarda ilişki daha güçlü)",
        "",
    ]

    pooled_dry = pooled_by_class(result, dry_only=True)
    if pooled_dry:
        pooled_all = pooled_by_class(result, dry_only=False)
        lines += [f"{'Sınıf':<16}{'kurak yıllar':>15}{'tüm yıllar':>14}", "-" * 45]
        for (code, dry_mean), (_, all_mean) in zip(pooled_dry, pooled_all):
            lines.append(f"{code} — {labels[code]:<11}{dry_mean:>15.4f}{all_mean:>14.4f}")
        gap = pooled_dry[-1][1] - pooled_dry[0][1]
        lines += [
            "-" * 45,
            f"Sınıf 5 eksi Sınıf 1 (beklenti NEGATİF): {gap:+.4f}"
            f"  -> {'beklenen yönde' if gap < 0 else 'TERS YÖNDE'}",
            "",
        ]

    lines.append("HİPOTEZ: yapısal risk, ağır stres altında daha güçlü ayrım üretmeli.")
    lines.append(f"SONUÇ  : {_verdict(result, MIN_DRY_YEARS, MIN_EFFECT_SIZE)}")
    return "\n".join(lines)


def _verdict(result: dict, min_dry: int, min_effect: float) -> str:
    dry, normal = result["dry"], result["normal"]
    if len(dry) < min_dry or not normal:
        return f"KARAR VERİLEMEZ — {len(dry)} kurak, {len(normal)} normal yıl."
    if result["dry_rho"] >= -min_effect:
        return (
            f"DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır "
            f"(ρ = {result['dry_rho']:+.3f}, eşik ≤ {-min_effect:.2f}). "
            "Harita ağır stres altında da etkilenen alanları göstermiyor."
        )
    if result["normal_rho"] - result["dry_rho"] < min_effect:
        return (
            "DESTEKLENMEDİ — kurak ve normal yıllarda ilişki benzer; "
            "harita stresi ayırt etmiyor."
        )
    return (
        "DESTEKLENDİ — ilişki kurak yıllarda belirgin şekilde güçlü. "
        "Harita, gerçek kuraklıkta etkilenen alanları ayırt ediyor."
    )
