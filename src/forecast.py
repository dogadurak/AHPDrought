"""Kuraklık tahmini — kalıcılık, sönümlü kalıcılık ve iklimatoloji.

Bu modülün asıl amacı bir tahmin üretmek DEĞİL, tahminin **ne kadar işe
yaradığını dürüstçe ölçmektir**.

## Neden taban çizgisi şart

Kuraklık güçlü otokorelasyonludur. "Üç ay sonra da bugünkü gibi olacak" demek
şaşırtıcı derecede iyi çalışır. Bu yüzden herhangi bir modelin becerisi, mutlak
hata değil, **taban çizgisine göre kazancı** ile ölçülmelidir:

    Beceri Skoru = 1 - MSE_model / MSE_taban

    > 0  taban çizgisinden iyi
    = 0  taban çizgisi kadar (yani model hiçbir şey katmıyor)
    < 0  taban çizgisinden KÖTÜ

İki taban çizgisi kullanılır:
  - **İklimatoloji**: her zaman SPI = 0 tahmin et. Bilgisiz referans.
  - **Kalıcılık**: bugünkü SPI'ı aynen tahmin et. Zorlu referans.

## Neden zamana göre bölme

Zaman serisinde rastgele eğitim/test ayrımı **veri sızıntısıdır**: komşu aylar
birbirine çok benzer, model onları ezberler ve skor gerçekte olmayan bir
başarıyı gösterir. Ayrım mutlaka kronolojik olmalıdır — geçmişle eğit,
gelecekte test et.

## Sönümlü kalıcılık

Saf kalıcılık uzun ufuklarda fazla iddialıdır. Optimal doğrusal tahmin, gecikme
korelasyonuyla sönümlenmiş halidir:

    SPI(t + h) ≈ ρ(h) · SPI(t)

ρ(h) EĞİTİM döneminden ölçülür, test döneminden değil. Bu, ekstra bilgi
kullanmadan kalıcılığı iyileştiren en basit gerçek modeldir.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ForecastSkill:
    """Bir tahmin yönteminin test dönemindeki performansı."""

    name: str
    lead_months: int
    n: int
    correlation: float
    rmse: float
    mae: float
    skill_vs_climatology: float
    skill_vs_persistence: float
    hit_rate_drought: float  # gerçek kuraklık aylarını yakalama oranı
    false_alarm_rate: float

    def row(self) -> str:
        return (
            f"{self.name:<22}{self.lead_months:>5}{self.n:>7}"
            f"{self.correlation:>9.3f}{self.rmse:>8.3f}"
            f"{self.skill_vs_climatology:>11.3f}{self.skill_vs_persistence:>12.3f}"
            f"{self.hit_rate_drought:>9.2f}{self.false_alarm_rate:>9.2f}"
        )


def chronological_split(series: pd.Series, train_fraction: float = 0.7) -> tuple[pd.Series, pd.Series]:
    """Seriyi zamana göre ikiye böler — asla rastgele değil.

    Rastgele bölme zaman serisinde sızıntı yaratır: komşu aylar birbirine
    bakar, model ezberler, skor şişer.
    """
    if not 0.3 <= train_fraction <= 0.9:
        raise ValueError(f"train_fraction 0.3-0.9 aralığında olmalı, {train_fraction} verildi")

    clean = series.dropna().sort_index()
    cut = int(len(clean) * train_fraction)
    if cut < 24 or len(clean) - cut < 24:
        raise ValueError(
            f"Bölme sonrası çok az veri kalıyor (eğitim {cut}, test {len(clean) - cut} ay). "
            "En az 24'er ay gerekir."
        )
    return clean.iloc[:cut], clean.iloc[cut:]


def climatology_forecast(index: pd.DatetimeIndex) -> pd.Series:
    """Bilgisiz taban çizgisi: SPI'ın beklenen değeri her zaman 0'dır."""
    return pd.Series(0.0, index=index)


def persistence_forecast(series: pd.Series, lead: int) -> pd.Series:
    """Bugünkü değeri `lead` ay sonrası için tahmin eder."""
    if lead < 1:
        raise ValueError(f"Tahmin ufku en az 1 ay olmalı, {lead} verildi")
    return series.shift(lead)


def lag_correlation(series: pd.Series, lead: int) -> float:
    """`lead` aylık gecikme korelasyonu (sönümleme katsayısı)."""
    shifted = series.shift(lead)
    both = pd.concat([series, shifted], axis=1).dropna()
    if len(both) < 12:
        return 0.0
    return float(both.corr().iloc[0, 1])


def damped_persistence_forecast(series: pd.Series, lead: int, rho: float) -> pd.Series:
    """Gecikme korelasyonuyla sönümlenmiş kalıcılık.

    `rho` EĞİTİM döneminden gelmelidir; test döneminden hesaplanırsa gelecekten
    bilgi sızdırılmış olur.
    """
    return series.shift(lead) * rho


def evaluate(
    truth: pd.Series,
    prediction: pd.Series,
    *,
    name: str,
    lead: int,
    drought_threshold: float = -1.0,
) -> ForecastSkill:
    """Bir tahmini iki taban çizgisine karşı değerlendirir."""
    frame = pd.concat([truth.rename("truth"), prediction.rename("pred")], axis=1).dropna()
    if frame.empty:
        raise ValueError(f"{name}: karşılaştırılacak ortak gözlem yok")

    y, p = frame["truth"].to_numpy(), frame["pred"].to_numpy()
    error = p - y

    mse = float(np.mean(error**2))
    mse_climatology = float(np.mean(y**2))  # iklimatoloji tahmini = 0
    persistence = truth.shift(lead).reindex(frame.index)
    joint = pd.concat([frame["truth"], persistence.rename("persist")], axis=1).dropna()
    mse_persistence = (
        float(np.mean((joint["persist"] - joint["truth"]) ** 2)) if not joint.empty else np.nan
    )

    predicted_drought = p <= drought_threshold
    actual_drought = y <= drought_threshold
    hits = int((predicted_drought & actual_drought).sum())
    false_alarms = int((predicted_drought & ~actual_drought).sum())

    return ForecastSkill(
        name=name,
        lead_months=lead,
        n=len(frame),
        correlation=float(np.corrcoef(y, p)[0, 1]) if np.std(p) > 0 else 0.0,
        rmse=float(np.sqrt(mse)),
        mae=float(np.mean(np.abs(error))),
        skill_vs_climatology=1 - mse / mse_climatology if mse_climatology > 0 else np.nan,
        skill_vs_persistence=(
            1 - mse / mse_persistence if mse_persistence and mse_persistence > 0 else np.nan
        ),
        hit_rate_drought=hits / actual_drought.sum() if actual_drought.sum() else np.nan,
        false_alarm_rate=(
            false_alarms / predicted_drought.sum() if predicted_drought.sum() else np.nan
        ),
    )


def run_benchmark(
    spi_series: pd.Series,
    *,
    leads: tuple[int, ...] = (1, 3, 6),
    train_fraction: float = 0.7,
    drought_threshold: float = -1.0,
) -> tuple[list[ForecastSkill], dict]:
    """Tüm yöntemleri tüm ufuklarda değerlendirir.

    Returns:
        (beceri satırları, eğitim döneminden öğrenilen parametreler)
    """
    train, test = chronological_split(spi_series, train_fraction)
    learned = {
        "train_span": (str(train.index[0].date()), str(train.index[-1].date())),
        "test_span": (str(test.index[0].date()), str(test.index[-1].date())),
        "rho": {},
    }

    full = spi_series.dropna().sort_index()
    rows: list[ForecastSkill] = []

    for lead in leads:
        rho = lag_correlation(train, lead)
        learned["rho"][lead] = rho

        # Tahminler tüm seride üretilir, ama YALNIZCA test döneminde puanlanır.
        truth = full.reindex(test.index)
        candidates = {
            "iklimatoloji": climatology_forecast(full.index),
            "kalıcılık": persistence_forecast(full, lead),
            f"sönümlü kalıcılık": damped_persistence_forecast(full, lead, rho),
        }
        for label, prediction in candidates.items():
            rows.append(
                evaluate(
                    truth,
                    prediction.reindex(test.index),
                    name=label,
                    lead=lead,
                    drought_threshold=drought_threshold,
                )
            )

    return rows, learned


def skill_table(rows: list[ForecastSkill], learned: dict) -> str:
    header = (
        f"{'Yöntem':<22}{'Ufuk':>5}{'n':>7}{'r':>9}{'RMSE':>8}"
        f"{'BS-iklim':>11}{'BS-kalıcı':>12}{'isabet':>9}{'yanlış':>9}"
    )
    lines = [
        f"Eğitim: {learned['train_span'][0]} - {learned['train_span'][1]}",
        f"Test  : {learned['test_span'][0]} - {learned['test_span'][1]}   (kronolojik bölme)",
        "",
        header,
        "-" * len(header),
    ]
    for row in rows:
        lines.append(row.row())
    lines += [
        "-" * len(header),
        # Konsol çıktısında ASCII tire kullanılır: Windows'un cp1254 kod sayfası
        # matematiksel eksi (U+2212) karakterini kodlayamaz ve betik çöker.
        "BS = Beceri Skoru (1 - MSE/MSE_referans). 0'in alti, referanstan kotu demektir.",
        "isabet = gerçek kurak ayların yakalanan oranı, yanlış = yanlış alarm oranı.",
        "",
        "Sönümleme katsayıları (eğitimden): "
        + ", ".join(f"ρ({k} ay)={v:.3f}" for k, v in learned["rho"].items()),
    ]
    return "\n".join(lines)
