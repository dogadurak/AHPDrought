"""Modül 1 — Kuraklık izleme: mevcut durumun taban çizgisine göre anomalisi.

Risk haritası "burası yapısal olarak dayanıksız" der; izleme modülü "bu yıl
fiilen ne oluyor" der. İkisi farklı sorulardır ve karıştırılmamalıdır.

İki ölçekte çalışır:

  MEKÂNSAL (30 m)  — Sentinel-2 NDVI'ın standartlaştırılmış anomalisi.
                     Hangi parseller bu yıl kendi normalinin altında?
  HAVZA (tek sayı) — 67 yıllık TerraClimate serisinden SPI.
                     Havza genelinde meteorolojik kuraklık var mı?

## Taban çizgisinin zayıf noktası (açıkça bildirilir)

Sentinel-2 arşivi 2015'te başlar; bu projede 2019-2024 kullanılıyor, yani
mekânsal anomalinin taban çizgisi **6 yıl**. Bir z-skoru için bu incedir:
standart sapma 6 örnekten kestirilirken kendisi de belirsizdir. Meteorolojik
anomali (SPI) 67 yıllık seriye dayandığı için çok daha sağlamdır. Mekânsal
katman "nerede", SPI "ne kadar" sorusuna güvenilir cevap verir — birlikte
okunmalıdırlar.

## Neden dışarıda-bırakmalı (leave-one-out) taban çizgisi

Hedef yılın kendisi taban çizgisine dahil edilirse, o yıl kendi ortalamasını
kendine doğru çeker ve anomali sistematik olarak KÜÇÜK çıkar. 6 yıllık bir
taban çizgisinde bu etki büyüktür (hedef yıl ortalamanın altıda birini
belirler). Bu yüzden her yılın anomalisi, o yıl hariç tutularak hesaplanır.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import Config
from .fetch.common import interim_path
from .grid import TargetGrid, read_grid_aligned

# Standartlaştırılmış anomali sınıfları (SPI eşikleriyle uyumlu).
ANOMALY_CLASSES = (
    (-np.inf, -2.0, "Olağanüstü altında"),
    (-2.0, -1.5, "Şiddetli altında"),
    (-1.5, -1.0, "Orta altında"),
    (-1.0, -0.5, "Hafif altında"),
    (-0.5, 0.5, "Normale yakın"),
    (0.5, 1.0, "Hafif üstünde"),
    (1.0, np.inf, "Belirgin üstünde"),
)

MIN_BASELINE_YEARS = 5

# Taban çizgisi standart sapması için ALT SINIR (NDVI birimi).
#
# Neden gerekli: z = (x − ortalama) / std. Bazı piksellerde 5 yıllık taban
# çizgisi neredeyse sabit çıkar (std ~ 1e-5) ve minik bir sapma devasa bir
# z-skoruna dönüşür. İlk çalıştırmada ölçülen aralık -411 .. +141 idi — bunlar
# kuraklık değil, sıfıra bölmenin gölgesi.
#
# 0.01 NDVI, Sentinel-2'nin bu ölçekteki gürültü tabanı mertebesindedir:
# altındaki değişkenlik ölçüm belirsizliğinden ayırt edilemez, dolayısıyla o
# pikselde "normalden sapma" tanımlamak anlamsızdır. Kırpmak yerine
# MASKELEMEK tercih edildi: uydurma bir değer üretmektense boşluk bırakmak.
MIN_BASELINE_STD = 0.01


@dataclass(frozen=True)
class AnomalyResult:
    """Bir yılın mekânsal NDVI anomalisi."""

    year: int
    z_score: np.ndarray
    baseline_years: tuple[int, ...]
    index_name: str
    masked_share: float = 0.0
    standardized: bool = True

    @property
    def unit(self) -> str:
        return "z" if self.standardized else f"{self.index_name.upper()} birimi"

    def class_shares(self) -> list[tuple[str, float]]:
        valid = self.z_score[np.isfinite(self.z_score)]
        total = valid.size
        shares = []
        for low, high, label in ANOMALY_CLASSES:
            share = float(((valid >= low) & (valid < high)).sum()) / total
            shares.append((label, share))
        return shares

    def summary(self) -> str:
        valid = self.z_score[np.isfinite(self.z_score)]
        lines = [
            f"{self.year} kurak dönem {self.index_name.upper()} anomalisi",
            f"  taban çizgisi: {list(self.baseline_years)} ({len(self.baseline_years)} yıl, "
            f"hedef yıl dışarıda)",
            f"  ortalama z    : {valid.mean():+.3f}",
            f"  aralık        : {valid.min():+.2f} .. {valid.max():+.2f}",
            f"  maskeli       : %{100 * self.masked_share:.2f} "
            f"(taban çizgisi sabit veya veri yok)",
            f"  normalin altı : %{100 * (valid < -0.5).mean():.1f} (z < -0.5)",
            f"  belirgin altı : %{100 * (valid < -1.0).mean():.1f} (z < -1.0)",
            "",
            f"  {'Sınıf':<22}{'Alan payı':>10}",
            "  " + "-" * 32,
        ]
        for label, share in self.class_shares():
            lines.append(f"  {label:<22}{f'%{100 * share:.1f}':>10}")
        return "\n".join(lines)


def _dry_season_layer(config: Config, grid: TargetGrid, year: int, index_name: str) -> np.ndarray:
    """Bir yılın kurak dönem aylık kompozitlerinin medyanı."""
    dry = config["periods"]["dry_season"]
    months = range(dry["start_month"], dry["end_month"] + 1)

    layers = []
    for month in months:
        path = interim_path(config, "ndvi_monthly", f"{index_name}_{year}_{month:02d}.tif")
        if not path.exists():
            continue
        array = read_grid_aligned(path, grid).astype("float32")
        layers.append(np.where(array == np.float32(config.nodata), np.nan, array))

    if not layers:
        raise FileNotFoundError(
            f"{year} kurak dönemi için {index_name} aylık kompoziti yok. "
            "Önce `python -m scripts.step02_fetch_data --only ndvi-dry` çalıştırın."
        )
    return np.nanmedian(np.stack(layers), axis=0)


def ndvi_anomaly(
    config: Config,
    grid: TargetGrid,
    year: int,
    *,
    index_name: str | None = None,
    min_years: int = MIN_BASELINE_YEARS,
    min_std: float = MIN_BASELINE_STD,
    standardize: bool = True,
) -> AnomalyResult:
    """Bir yılın kurak dönem NDVI'ının, diğer yıllara göre z-skoru.

    Taban çizgisi hedef yılı DIŞLAR (leave-one-out) — aksi halde yıl kendi
    ortalamasını kendine çeker ve anomali küçük görünür.

    Taban çizgisi standart sapması `min_std`in altında kalan pikseller
    maskelenir: orada z-skoru sıfıra bölmeye yaklaşır ve anlamsız uç değerler
    üretir (bkz. MIN_BASELINE_STD).

    Args:
        standardize: True ise z-skoru (sapma / kendi std'si), False ise HAM
            fark (NDVI birimi) döndürür.

            Bu ayrım önemli. z-skoru her pikseli kendi değişkenliğine böler;
            yapısal olarak kurak bir piksel zaten hep kuraktır, varyansı
            düşüktür ve büyük bir z üretemez. Orman ya da sulanan tarımın ise
            kaybedecek NDVI'ı vardır. Sonuç: z-skoru, yapısal riskle TERS
            yönde çalışabilir ve risk haritasının sınamasını sistematik olarak
            bozar. Ham fark bu yanlılığı taşımaz — "kaç NDVI birimi kaybedildi"
            sorusunu doğrudan sorar.
    """
    index_name = index_name or config["data_sources"]["sentinel2"].get("vegetation_index", "ndvi")
    reference_years = [y for y in config["periods"]["reference_years"] if y != year]

    if len(reference_years) < min_years:
        raise ValueError(
            f"Taban çizgisi {len(reference_years)} yıl — anlamlı bir z-skoru için "
            f"en az {min_years} yıl gerekir. periods.reference_years genişletilmeli."
        )

    target = _dry_season_layer(config, grid, year, index_name)
    baseline = np.stack([_dry_season_layer(config, grid, y, index_name) for y in reference_years])

    mean = np.nanmean(baseline, axis=0)
    std = np.nanstd(baseline, axis=0, ddof=1)

    difference = target - mean
    if standardize:
        unstable = ~(std > min_std)
        with np.errstate(invalid="ignore", divide="ignore"):
            z = np.where(unstable, np.nan, difference / std)
    else:
        # Ham farkta sıfıra bölme yok; yalnızca veri boşlukları maskeli.
        unstable = np.zeros_like(difference, dtype=bool)
        z = difference

    masked_share = float(np.isnan(z).mean())
    unstable_share = float(unstable[np.isfinite(std)].mean()) if np.isfinite(std).any() else 0.0
    if unstable_share > 0:
        print(
            f"      taban çizgisi std < {min_std} olduğu için maskelenen: "
            f"%{100 * unstable_share:.2f} (z-skoru orada tanımsız)"
        )

    return AnomalyResult(
        year=year,
        z_score=z.astype("float32"),
        baseline_years=tuple(reference_years),
        index_name=index_name,
        masked_share=masked_share,
        standardized=standardize,
    )


def anomaly_by_landcover(
    config: Config, grid: TargetGrid, result: AnomalyResult
) -> list[tuple[str, float, int]]:
    """Anomaliyi arazi örtüsü sınıfına göre özetler — kim etkilendi?"""
    from .config import load_json

    codes = read_grid_aligned(interim_path(config, "landcover.tif"), grid)
    lookup = load_json(config["data_sources"]["landcover"]["lookup_file"])["classes"]

    rows = []
    for code_str, entry in lookup.items():
        if entry.get("score") is None:
            continue
        selection = (codes == int(code_str)) & np.isfinite(result.z_score)
        if selection.sum() < 1000:
            continue
        rows.append((entry["name"], float(np.nanmean(result.z_score[selection])), int(selection.sum())))
    return sorted(rows, key=lambda r: r[1])


def anomaly_by_risk_class(
    config: Config, grid: TargetGrid, result: AnomalyResult, risk_classes: np.ndarray
) -> list[tuple[int, float, int]]:
    """Anomaliyi risk sınıfına göre özetler.

    Bu, risk haritasının OPERASYONEL sınamasıdır: yüksek riskli sınıflandırılan
    alanlar, kurak bir yılda gerçekten daha fazla mı etkileniyor? Beklenti,
    risk sınıfı arttıkça anomalinin daha negatif olması.
    """
    rows = []
    for code in range(1, config["classification"]["n_classes"] + 1):
        selection = (risk_classes == code) & np.isfinite(result.z_score)
        if selection.sum() == 0:
            continue
        rows.append((code, float(np.nanmean(result.z_score[selection])), int(selection.sum())))
    return rows
