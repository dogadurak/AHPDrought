"""Mevsimsel öngörü — kış sonu durumundan yaz stresi.

## Neden ilk kurgu yanlıştı

İlk denemede "SPI-3'ten 3 ay sonraki SPI-3" soruldu ve beklendiği gibi hiçbir
beceri çıkmadı. Sebep matematiksel: ay *t* için SPI-3, *t−2…t* penceresini
toplar; *t+3* için *t+1…t+3*'ü. **İki pencere hiç kesişmez**, dolayısıyla
paylaşılacak bilgi yoktur. Bu, veriyle ilgili bir bulgu değil, sorunun kötü
kurulmuş olmasıydı.

## Doğru soru

Akdeniz ikliminde yaz yağışsızdır — Gediz'de temmuz-ağustos iklimatolojisi
3-5 mm. Yani yaz bitki örtüsünü belirleyen şey **o yaz yağan yağmur değil,
kışın toprakta ve rezervuarda biriken sudur**. Fiziksel olarak öngörülebilir
olan bağ budur:

    Kış sonu su durumu  ──►  Yaz su stresi
    (nisan sonunda bilinir)   (temmuz-eylül'de yaşanır)

Bu, 3 ay ilerisi için **anlamlı ve fiziksel** bir tahmin sorusudur; SPI
pencerelerinin mekanik kaydırılması değildir.

## Değerlendirme kuralları değişmedi

Aynı katılıkta: kronolojik bölme, iklimatoloji ve kalıcılık taban çizgileri,
parametreler yalnızca eğitim döneminden. Fiziksel gerekçe, beceri kanıtının
yerine geçmez — yalnızca doğru soruyu sormamızı sağlar.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SeasonalDataset:
    """Yıl bazında öngörücüler ve hedef."""

    predictors: pd.DataFrame  # satır = yıl
    target: pd.Series
    target_name: str
    predictor_season: str
    target_season: str

    def describe(self) -> str:
        lines = [
            f"Öngörücüler ({self.predictor_season}): {', '.join(self.predictors.columns)}",
            f"Hedef ({self.target_season}): {self.target_name}",
            f"Yıl sayısı: {len(self.target)} ({self.target.index.min()}-{self.target.index.max()})",
            "",
            f"{'Öngörücü':<24}{'hedefle r':>11}{'Spearman':>11}",
            "-" * 46,
        ]
        for column in self.predictors.columns:
            joint = pd.concat([self.predictors[column], self.target], axis=1).dropna()
            pearson = float(joint.corr().iloc[0, 1])
            spearman = float(joint.corr(method="spearman").iloc[0, 1])
            lines.append(f"{column:<24}{pearson:>11.3f}{spearman:>11.3f}")
        return "\n".join(lines)


def seasonal_mean(series: pd.Series, months: tuple[int, ...], *, how: str = "mean") -> pd.Series:
    """Her yıl için belirli ayların özeti; indeks = yıl."""
    selected = series[series.index.month.isin(months)]
    grouped = selected.groupby(selected.index.year)
    return getattr(grouped, how)()


def build_dataset(
    frame: pd.DataFrame,
    *,
    predictor_months: tuple[int, ...] = (3, 4),
    target_months: tuple[int, ...] = (7, 8, 9),
    target_column: str = "soil",
) -> SeasonalDataset:
    """Kış sonu öngörücüleri ile yaz hedefini yıl bazında eşler.

    Args:
        predictor_months: Öngörücünün bilindiği aylar. Varsayılan mart-nisan:
            yaş mevsim bitmiş, yaz henüz başlamamıştır — yani tahmin gerçekten
            ileriye dönüktür, hedef dönemden bilgi sızmaz.
        target_months: Hedef dönem (kurak mevsim).
        target_column: Yaz stresinin ölçüsü. `soil` (kök bölgesi nemi) tercih
            edilir: tarımsal etkiye en yakın büyüklük odur.
    """
    overlap = set(predictor_months) & set(target_months)
    if overlap:
        raise ValueError(
            f"Öngörücü ve hedef ayları kesişiyor {sorted(overlap)} — bu, hedeften "
            "öngörücüye bilgi sızdırır ve beceriyi yapay olarak yükseltir."
        )
    if max(predictor_months) >= min(target_months):
        raise ValueError(
            f"Öngörücü ayları ({predictor_months}) hedeften ({target_months}) önce "
            "bitmelidir; aksi halde tahmin ileriye dönük değildir."
        )

    predictors = {}
    if "ppt" in frame:
        # Yaş mevsim toplam yağışı: kasım-nisan, kışın biriken su.
        wet = frame["ppt"][frame["ppt"].index.month.isin((11, 12, 1, 2, 3, 4))]
        # Kasım-aralık bir SONRAKİ yılın yaz mevsimini besler.
        water_year = np.where(wet.index.month >= 11, wet.index.year + 1, wet.index.year)
        predictors["yas_mevsim_yagisi"] = wet.groupby(water_year).sum()
        predictors["ilkbahar_yagisi"] = seasonal_mean(frame["ppt"], predictor_months, how="sum")
    if "soil" in frame:
        predictors["ilkbahar_toprak_nemi"] = seasonal_mean(frame["soil"], predictor_months)
    if "pdsi" in frame:
        predictors["ilkbahar_pdsi"] = seasonal_mean(frame["pdsi"], predictor_months)
    if "pet" in frame:
        predictors["ilkbahar_pet"] = seasonal_mean(frame["pet"], predictor_months, how="sum")

    if target_column not in frame:
        raise KeyError(f"Hedef sütun '{target_column}' seride yok: {list(frame.columns)}")
    target = seasonal_mean(frame[target_column], target_months)

    table = pd.DataFrame(predictors).dropna(how="all")
    common = table.index.intersection(target.index)
    return SeasonalDataset(
        predictors=table.loc[common],
        target=target.loc[common],
        target_name=f"yaz {target_column}",
        predictor_season=f"{predictor_months} ayları",
        target_season=f"{target_months} ayları",
    )


@dataclass(frozen=True)
class SeasonalSkill:
    name: str
    n_test: int
    correlation: float
    rmse: float
    skill_vs_climatology: float
    skill_vs_persistence: float

    def row(self) -> str:
        return (
            f"{self.name:<30}{self.n_test:>7}{self.correlation:>10.3f}"
            f"{self.rmse:>10.3f}{self.skill_vs_climatology:>12.3f}"
            f"{self.skill_vs_persistence:>13.3f}"
        )


def evaluate_seasonal(
    dataset: SeasonalDataset,
    *,
    train_fraction: float = 0.7,
    predictors: tuple[str, ...] | None = None,
) -> tuple[list[SeasonalSkill], dict]:
    """Kış sonu öngörücülerinden yaz hedefini tahmin eder ve beceriyi ölçer.

    Model kasten en basit haliyle tutulur (tek değişkenli doğrusal regresyon):
    amaç en iyi tahmini bulmak değil, **fiziksel bağın öngörü değeri taşıyıp
    taşımadığını** göstermektir. Karmaşık bir model, az sayıda yılla aşırı
    uyum riski taşır ve sonucu yorumlanamaz kılar.
    """
    target = dataset.target.dropna()
    cut = int(len(target) * train_fraction)
    if cut < 15 or len(target) - cut < 10:
        raise ValueError(
            f"Bölme sonrası çok az yıl kalıyor (eğitim {cut}, test {len(target) - cut}). "
            "Daha uzun bir seri gerekir."
        )

    train_years, test_years = target.index[:cut], target.index[cut:]
    learned = {
        "train_span": (int(train_years[0]), int(train_years[-1])),
        "test_span": (int(test_years[0]), int(test_years[-1])),
        "fits": {},
    }

    truth = target.loc[test_years]
    climatology = float(target.loc[train_years].mean())
    mse_climatology = float(((truth - climatology) ** 2).mean())

    # Kalıcılık: bu yılın yazı, geçen yılın yazı gibi olur.
    persistence = target.shift(1).loc[test_years]
    joint = pd.concat([truth, persistence.rename("p")], axis=1).dropna()
    mse_persistence = float(((joint["p"] - joint.iloc[:, 0]) ** 2).mean()) if not joint.empty else np.nan

    rows = [
        SeasonalSkill("iklimatoloji (eğitim ort.)", len(truth), 0.0,
                      float(np.sqrt(mse_climatology)), 0.0,
                      1 - mse_climatology / mse_persistence if mse_persistence else np.nan),
    ]
    if not joint.empty:
        rows.append(
            SeasonalSkill(
                "kalıcılık (geçen yaz)", len(joint),
                float(joint.corr().iloc[0, 1]), float(np.sqrt(mse_persistence)),
                1 - mse_persistence / mse_climatology if mse_climatology else np.nan, 0.0,
            )
        )

    names = predictors or tuple(dataset.predictors.columns)
    for name in names:
        column = dataset.predictors[name]
        fit_frame = pd.concat([column.rename("x"), target.rename("y")], axis=1).dropna()
        train_frame = fit_frame.loc[fit_frame.index.intersection(train_years)]
        test_frame = fit_frame.loc[fit_frame.index.intersection(test_years)]
        if len(train_frame) < 15 or len(test_frame) < 8:
            continue

        # Katsayılar YALNIZCA eğitim döneminden.
        slope, intercept = np.polyfit(train_frame["x"], train_frame["y"], 1)
        learned["fits"][name] = {"slope": float(slope), "intercept": float(intercept)}

        prediction = slope * test_frame["x"] + intercept
        error = prediction - test_frame["y"]
        mse = float((error**2).mean())
        mse_clim_here = float(((test_frame["y"] - climatology) ** 2).mean())

        rows.append(
            SeasonalSkill(
                name, len(test_frame),
                float(np.corrcoef(test_frame["y"], prediction)[0, 1]),
                float(np.sqrt(mse)),
                1 - mse / mse_clim_here if mse_clim_here else np.nan,
                1 - mse / mse_persistence if mse_persistence else np.nan,
            )
        )

    return rows, learned


def seasonal_skill_table(rows: list[SeasonalSkill], learned: dict, dataset: SeasonalDataset) -> str:
    header = (
        f"{'Yöntem / öngörücü':<30}{'n':>7}{'r':>10}{'RMSE':>10}"
        f"{'BS-iklim':>12}{'BS-kalici':>13}"
    )
    lines = [
        f"Hedef : {dataset.target_name}  ({dataset.target_season})",
        f"Girdi : {dataset.predictor_season} sonunda bilinen durum",
        f"Egitim: {learned['train_span'][0]}-{learned['train_span'][1]}   "
        f"Test: {learned['test_span'][0]}-{learned['test_span'][1]}  (kronolojik)",
        "",
        header,
        "-" * len(header),
    ]
    lines += [row.row() for row in rows]
    lines += [
        "-" * len(header),
        "BS = Beceri Skoru (1 - MSE/MSE_referans). 0'in alti referanstan kotu.",
        "Bir ongorucunun HEM iklimatolojiyi HEM kaliciligi gecmesi gerekir.",
    ]
    return "\n".join(lines)
