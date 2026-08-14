"""Risk haritasının çok yıllı operasyonel sınaması.

## İlk sınama neden zayıftı

İlk sürümde tek bir yılın (2024) NDVI anomalisi, risk sınıflarına göre
özetlendi ve monoton çıkmadığı için "doğrulanmadı" denildi. İki kusuru vardı:

  1. **Tek yıl.** Dokuz yıllık veriden bir yıl seçmek, elde olan bilginin
     sekizde birini kullanmaktır.
  2. **Yanlış beklenti.** Yapısal bir duyarlılık haritasının, HER yıl impact
     öngörmesi beklenemez. Yağışlı bir yılda kimse zorlanmaz; duyarlılık
     farkı görünmez. Harita, ancak **stres varken** ayrım üretmelidir.

## Doğru sınama

Sınanabilir ve yanlışlanabilir hipotez:

    Yapısal risk ile gözlenen bitki örtüsü kaybı arasındaki ilişki,
    KURAK yıllarda yağışlı yıllara göre belirgin şekilde güçlü olmalıdır.

Yıllar kurak/yağışlı diye, modele hiç girmemiş bir ölçütle (havza SPI'ı)
etiketlenir. Sonra her yıl için risk-anomali sıra korelasyonu hesaplanır ve
iki grup karşılaştırılır.

Hipotez yanlışlanabilir: kurak ve yağışlı yıllarda korelasyon aynı çıkarsa,
harita stresi ayırt etmiyor demektir ve bu, raporlanması gereken olumsuz bir
sonuçtur.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from .config import Config
from .grid import TargetGrid


# Hipotez hakkında karar verebilmek için gereken en az kurak yıl sayısı.
# Tek yılla yapılan karşılaştırma, o yılın tesadüfünü sonuç sanmaktır.
MIN_DRY_YEARS = 3

# Anlamlı sayılacak en küçük etki büyüklüğü (Spearman ρ birimi). Bunun
# altındaki farklar, milyonlarca pikselde istatistiksel olarak "anlamlı"
# görünse bile pratikte sıfırdan ayırt edilemez.
MIN_EFFECT_SIZE = 0.10


@dataclass(frozen=True)
class YearOutcome:
    """Bir yılın anomalisi ve risk haritasıyla ilişkisi."""

    year: int
    spi: float
    is_dry: bool
    mean_anomaly: float
    rank_correlation: float
    class_means: list[tuple[int, float, int]]
    monotone: bool


@dataclass(frozen=True)
class OperationalTest:
    outcomes: list[YearOutcome]
    dry_threshold: float

    @property
    def dry(self) -> list[YearOutcome]:
        return [o for o in self.outcomes if o.is_dry]

    @property
    def wet(self) -> list[YearOutcome]:
        return [o for o in self.outcomes if not o.is_dry]

    def summary(self) -> str:
        lines = [
            f"{'Yıl':<6}{'SPI':>7}{'durum':>10}{'ort. anomali':>15}{'risk-anomali ρ':>17}{'monoton':>10}",
            "-" * 65,
        ]
        for o in sorted(self.outcomes, key=lambda x: x.year):
            lines.append(
                f"{o.year:<6}{o.spi:>7.2f}{'KURAK' if o.is_dry else 'yağışlı':>10}"
                f"{o.mean_anomaly:>15.3f}{o.rank_correlation:>17.4f}"
                f"{'evet' if o.monotone else 'hayır':>10}"
            )
        lines.append("-" * 65)

        dry, wet = self.dry, self.wet
        if not dry or not wet:
            lines.append(
                f"Kurak yıl {len(dry)}, yağışlı yıl {len(wet)} — karşılaştırma yapılamıyor."
            )
            return "\n".join(lines)

        dry_rho = float(np.mean([o.rank_correlation for o in dry]))
        wet_rho = float(np.mean([o.rank_correlation for o in wet]))
        gap = wet_rho - dry_rho

        lines += [
            f"Kurak yıllar   (n={len(dry)}): ortalama ρ = {dry_rho:+.4f}"
            f"   [{', '.join(str(o.year) for o in dry)}]",
            f"Yağışlı yıllar (n={len(wet)}): ortalama ρ = {wet_rho:+.4f}"
            f"   [{', '.join(str(o.year) for o in wet)}]",
            f"Fark: {gap:+.4f}  (pozitif = kurak yıllarda ilişki daha güçlü)",
            "",
            "HİPOTEZ: yapısal risk, stres varken daha güçlü ayrım üretmeli.",
            f"SONUÇ  : {self._verdict(dry_rho, wet_rho)}",
        ]
        return "\n".join(lines)

    def _verdict(self, dry_rho: float, wet_rho: float) -> str:
        """Hipotezin desteklenip desteklenmediğine karar verir.

        Eşikler kasten katı. İlk sürümde yalnızca "kurak ρ negatif mi" ve
        "fark > 0.02 mi" bakılıyordu; tek bir kurak yılla (n=1) ve ρ = −0.04
        gibi fiilen sıfır bir değerle "DESTEKLENDİ" çıkabiliyordu. Bu, tez
        savunmasında ilk soruda çökecek türden bir sonuçtu.
        """
        if len(self.dry) < MIN_DRY_YEARS:
            return (
                f"KARAR VERİLEMEZ — yalnızca {len(self.dry)} kurak yıl var "
                f"(en az {MIN_DRY_YEARS} gerekir). Uydu arşivi bu havzanın "
                "şiddetli kuraklıklarıyla örtüşmüyor."
            )
        if dry_rho >= -MIN_EFFECT_SIZE:
            return (
                f"DESTEKLENMEDİ — kurak yıllarda ilişki fiilen sıfır "
                f"(ρ = {dry_rho:+.3f}, anlamlı sayılması için ≤ {-MIN_EFFECT_SIZE:.2f} "
                "olmalıydı). Harita etkilenen alanları göstermiyor."
            )
        if wet_rho - dry_rho < MIN_EFFECT_SIZE:
            return (
                "DESTEKLENMEDİ — kurak ve yağışlı yıllarda ilişki benzer, "
                "harita stresi ayırt etmiyor."
            )
        return (
            "DESTEKLENDİ — ilişki kurak yıllarda belirgin şekilde güçlü, "
            "yani harita stres altında ayrım üretiyor."
        )


LABEL_METHODS = ("spring_soil", "wet_season_precip", "summer_spi")


def label_dry_years(
    series: pd.Series,
    years: list[int],
    *,
    method: str = "spring_soil",
    threshold: float = -0.5,
) -> dict[int, tuple[float, bool]]:
    """Yılları kurak/yağışlı diye etiketler.

    Etiket, risk haritasından ve NDVI'dan BAĞIMSIZ bir ölçüte dayanır
    (meteoroloji/toprak). Aksi halde sınama kendi kendini doğrulardı.

    ## Yöntem seçimi neden önemli — ölçülen sonuç

    Aynı 9 yıl, üç farklı ölçütle etiketlendiğinde:

        yaz SPI-3        -> kurak yıl: 2025                          (n=1)
        yaş mevsim yağışı-> 2017, 2018, 2020, 2023                   (n=4)
        ilkbahar toprak  -> 2017, 2018, 2019, 2022, 2024, 2025       (n=6)

    **Yaz SPI'ı bu iklimde bilgi taşımaz.** Gediz'de temmuz-ağustos
    iklimatolojisi 8 mm'dir; yazın "az yağması" her yıl olan şeydir ve o yılın
    tarımsal olarak kurak geçtiğini göstermez. Yazın SPI'ı standartlaştırılmış
    olsa bile, neredeyse sıfır olan bir büyüklüğün oranını ölçer.

    **Doğru ölçüt ilkbahar toprak nemidir** ve bu keyfî bir tercih değil:
    Adım 12'de 68 yıllık veriyle, kronolojik bölme ve iki taban çizgisine karşı
    ölçüldüğünde yaz su stresini en iyi öngören değişken tam olarak buydu
    (iklimatolojiye karşı beceri +0.445, kalıcılığa karşı +0.732). Yani
    "kurak yıl" tanımı, bağımsız olarak doğrulanmış fiziksel bağa dayanıyor.

    Args:
        series: `method`e göre beklenen seri — `spring_soil` için toprak nemi,
            `wet_season_precip` ve `summer_spi` için yağış/SPI.
        method: LABEL_METHODS içinden biri.
        threshold: Standartlaştırılmış değerin bu eşiğin altı "kurak" sayılır.
    """
    if method not in LABEL_METHODS:
        raise ValueError(f"Bilinmeyen etiketleme yöntemi '{method}'. Seçenekler: {LABEL_METHODS}")

    index = series.index
    if method == "summer_spi":
        selected = series[index.month.isin((7, 8, 9))]
        by_year = selected.groupby(selected.index.year).mean()
    elif method == "wet_season_precip":
        wet = series[index.month.isin((11, 12, 1, 2, 3, 4))]
        # Kasım-aralık yağışı BİR SONRAKİ yazı besler (su yılı kaydırması).
        water_year = np.where(wet.index.month >= 11, wet.index.year + 1, wet.index.year)
        totals = wet.groupby(water_year).sum()
        by_year = (totals - totals.mean()) / totals.std()
    else:  # spring_soil
        spring = series[index.month.isin((3, 4))]
        means = spring.groupby(spring.index.year).mean()
        by_year = (means - means.mean()) / means.std()

    labels = {}
    for year in years:
        value = float(by_year.get(year, np.nan))
        labels[year] = (value, bool(np.isfinite(value) and value <= threshold))
    return labels


def run_operational_test(
    config: Config,
    grid: TargetGrid,
    risk_index: np.ndarray,
    risk_classes: np.ndarray,
    label_series: pd.Series,
    *,
    dry_threshold: float = -0.5,
    standardize: bool = True,
    landcover_code: int | None = None,
    label_method: str = "spring_soil",
    min_irrigation_distance_m: float | None = None,
) -> OperationalTest:
    """Her referans yılı için anomaliyi hesaplayıp risk haritasıyla ilişkilendirir.

    Args:
        standardize: z-skoru mu (True) ham NDVI farkı mı (False) kullanılsın.
        landcover_code: Verilirse yalnızca bu arazi örtüsü sınıfındaki
            pikseller kullanılır (ör. 40 = Cropland).

            **Neden gerekli.** NDVI kaybı, farklı bitki yoğunluklarındaki
            alanlar arasında adil bir etki ölçüsü değildir: NDVI'ı zaten 0.15
            olan çıplak bir piksel 0.3 birim kaybedemez, ormanın ise kaybedecek
            çok şeyi vardır. Bu taban/tavan etkisi hem ham farkta hem z-skorunda
            vardır ve yüksek riskli (seyrek örtülü) alanları sistematik olarak
            "az etkilenmiş" gösterir. Havza genelinde ölçülen ters yönlü ilişki
            büyük ölçüde bundan kaynaklanır.

            Tek bir arazi örtüsü sınıfı içinde karşılaştırma yapmak bu
            yanlılığı ortadan kaldırır: benzer yoğunluktaki parseller
            birbiriyle kıyaslanır. Tarımsal kuraklık çalışması olduğu için
            doğal seçim `Cropland`tir.
    """
    from .fetch.common import interim_path
    from .grid import read_grid_aligned
    from .monitor import anomaly_by_risk_class, ndvi_anomaly
    from .validate import rank_correlation

    years = list(config["periods"]["reference_years"])
    labels = label_dry_years(
        label_series, years, method=label_method, threshold=dry_threshold
    )

    selection_mask = None
    if landcover_code is not None:
        codes = read_grid_aligned(interim_path(config, "landcover.tif"), grid)
        selection_mask = codes == landcover_code

    if min_irrigation_distance_m is not None:
        # Sulanan parselde NDVI kuraklıkta da korunur; sinyal ancak YAĞMURA
        # BAĞLI tarımda görünür. Ölçülen fark için modül başlığına bakın.
        distance = read_grid_aligned(
            interim_path(config, "distance_to_irrigation.tif"), grid
        ).astype("float32")
        distance = np.where(distance == np.float32(config.nodata), np.nan, distance)
        rainfed = distance >= min_irrigation_distance_m
        selection_mask = rainfed if selection_mask is None else (selection_mask & rainfed)

    if selection_mask is not None:
        print(f"      seçilen alan: {int(selection_mask.sum()):,} piksel "
              f"(%{100 * selection_mask.mean():.1f})")

    outcomes = []
    for year in years:
        try:
            anomaly = ndvi_anomaly(config, grid, year, standardize=standardize)
        except (FileNotFoundError, ValueError) as exc:
            print(f"      {year}: atlandı ({exc})")
            continue

        if selection_mask is not None:
            filtered = np.where(selection_mask, anomaly.z_score, np.nan).astype("float32")
            anomaly = replace(anomaly, z_score=filtered)

        rows = anomaly_by_risk_class(config, grid, anomaly, risk_classes)
        spi_value, is_dry = labels[year]
        valid = np.isfinite(anomaly.z_score)

        outcomes.append(
            YearOutcome(
                year=year,
                spi=spi_value,
                is_dry=is_dry,
                mean_anomaly=float(np.nanmean(anomaly.z_score[valid])),
                rank_correlation=rank_correlation(risk_index, anomaly.z_score),
                class_means=rows,
                monotone=all(rows[i][1] >= rows[i + 1][1] for i in range(len(rows) - 1)),
            )
        )
        print(
            f"      {year}: SPI {spi_value:+.2f} "
            f"({'kurak' if is_dry else 'yağışlı'})  ρ = {outcomes[-1].rank_correlation:+.4f}"
        )

    if not outcomes:
        raise RuntimeError("Hiçbir yıl için anomali hesaplanamadı")
    return OperationalTest(outcomes=outcomes, dry_threshold=dry_threshold)


def pooled_class_means(test: OperationalTest, *, dry_only: bool = True) -> list[tuple[int, float]]:
    """Seçili yılların risk sınıfı ortalamalarını birleştirir.

    Kurak yıllar havuzlandığında sınıflar arası fark, tek yıla göre çok daha
    az gürültülüdür — asıl sinyal burada görünür.
    """
    selected = test.dry if dry_only else test.outcomes
    if not selected:
        return []

    totals: dict[int, list[float]] = {}
    weights: dict[int, list[int]] = {}
    for outcome in selected:
        for code, mean_z, count in outcome.class_means:
            totals.setdefault(code, []).append(mean_z * count)
            weights.setdefault(code, []).append(count)

    return [
        (code, float(np.sum(totals[code]) / np.sum(weights[code])))
        for code in sorted(totals)
    ]
