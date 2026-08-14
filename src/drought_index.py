"""Standartlaştırılmış Yağış İndeksi (SPI) — McKee ve ark. (1993).

SPI, bir yerin yağışının kendi geçmişine göre ne kadar sıra dışı olduğunu
söyler. Mutlak milimetre yerine standart sapma birimiyle konuşur, bu yüzden
çöl ile Karadeniz kıyısı aynı ölçekte karşılaştırılabilir.

Hesap üç adımdır:

  1. Yağışı `scale` ay boyunca biriktir (SPI-3 = son 3 ayın toplamı).
  2. Her TAKVİM AYI için ayrı gama dağılımı uyarla. Ayrı ayrı yapılması şart:
     Akdeniz ikliminde ağustosun 2 mm'si normal, ocağın 2 mm'si felakettir.
     Tek dağılım uyarlamak mevsimselliği kuraklık sanmaya yol açar.
  3. Kümülatif olasılığı standart normal kuantile çevir.

**Sıfır yağış sorunu.** Gama dağılımı sıfırda tanımsızdır ve Gediz'de ağustos
ayları çoğunlukla tamamen kurudur. Thom (1958) karma dağılım çözümü:

    H(x) = q + (1 − q) · G(x),    q = P(yağış = 0)

Bu düzeltme yapılmazsa kurak bölgelerde yaz SPI'ı sistematik olarak yanlış
çıkar — literatürde sık rastlanan bir hatadır.

Kaynak:
  McKee, T. B., Doesken, N. J. & Kleist, J. (1993). The relationship of drought
  frequency and duration to time scales. *8th Conference on Applied
  Climatology*, 179–184.
  Thom, H. C. S. (1958). A note on the gamma distribution. *Monthly Weather
  Review*, 86(4), 117–122.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# McKee ve ark. (1993) kuraklık sınıfları.
SPI_CATEGORIES = (
    (-np.inf, -2.0, "Olağanüstü kurak"),
    (-2.0, -1.5, "Şiddetli kurak"),
    (-1.5, -1.0, "Orta kurak"),
    (-1.0, -0.5, "Hafif kurak"),
    (-0.5, 0.5, "Normale yakın"),
    (0.5, 1.0, "Hafif nemli"),
    (1.0, 1.5, "Orta nemli"),
    (1.5, 2.0, "Çok nemli"),
    (2.0, np.inf, "Olağanüstü nemli"),
)

MIN_CALIBRATION_YEARS = 30  # WMO önerisi


@dataclass(frozen=True)
class SPIResult:
    """SPI serisi ve nasıl üretildiğine dair kayıt."""

    values: pd.Series
    scale: int
    calibration: tuple[str, str]
    zero_fraction: dict[int, float]  # takvim ayı -> kuru ay oranı

    def categories(self) -> pd.Series:
        return self.values.map(classify_spi)

    def summary(self) -> str:
        v = self.values.dropna()
        drought = (v <= -1.0).mean()
        severe = (v <= -1.5).mean()
        lines = [
            f"SPI-{self.scale}  ({self.calibration[0]} - {self.calibration[1]} kalibrasyonu)",
            f"  gözlem      : {v.size} ay",
            f"  ortalama    : {v.mean():+.3f}   (teorik 0)",
            f"  std sapma   : {v.std():.3f}   (teorik 1)",
            f"  aralık      : {v.min():+.2f} .. {v.max():+.2f}",
            f"  kurak ay    : %{100 * drought:.1f}  (SPI <= -1)",
            f"  şiddetli    : %{100 * severe:.1f}  (SPI <= -1.5)",
        ]
        dry = {m: f"%{100 * f:.0f}" for m, f in self.zero_fraction.items() if f > 0}
        if dry:
            lines.append(f"  tamamen kuru geçen aylar: {dry}")
        return "\n".join(lines)


def classify_spi(value: float) -> str:
    if not np.isfinite(value):
        return "veri yok"
    for low, high, label in SPI_CATEGORIES:
        if low <= value < high:
            return label
    return "Olağanüstü nemli"


def accumulate(precipitation: pd.Series, scale: int) -> pd.Series:
    """Yağışı `scale` ay boyunca biriktirir (kayan toplam)."""
    if scale < 1:
        raise ValueError(f"Ölçek en az 1 ay olmalı, {scale} verildi")
    if not isinstance(precipitation.index, pd.DatetimeIndex):
        raise TypeError("Yağış serisi DatetimeIndex taşımalı")
    return precipitation.rolling(window=scale, min_periods=scale).sum()


def spi(
    precipitation: pd.Series,
    scale: int = 3,
    *,
    calibration: tuple[str, str] | None = None,
    min_years: int = MIN_CALIBRATION_YEARS,
) -> SPIResult:
    """Aylık yağış serisinden SPI hesaplar.

    Args:
        precipitation: Aylık toplam yağış (mm), DatetimeIndex ile.
        scale: Biriktirme penceresi (ay). SPI-3 tarımsal, SPI-12 hidrolojik
            kuraklık için kullanılır.
        calibration: Dağılımın uyarlanacağı dönem ("1961", "1990") gibi.
            None ise tüm seri kullanılır.
        min_years: Bu kadar yıldan kısa kalibrasyon reddedilir.

    ÖNEMLİ: Kalibrasyon dönemi ile değerlendirme dönemi ayrıldığında bile SPI
    "geriye dönük" bir indekstir — tahmin değildir. Tahmin için
    `src/forecast.py`ye bakın.
    """
    from scipy.stats import gamma, norm

    series = precipitation.dropna().sort_index()
    accumulated = accumulate(series, scale)

    if calibration is None:
        calibration_mask = pd.Series(True, index=accumulated.index)
        span = (str(accumulated.index.min().date()), str(accumulated.index.max().date()))
    else:
        start, end = calibration
        calibration_mask = (accumulated.index >= start) & (accumulated.index <= end)
        calibration_mask = pd.Series(calibration_mask, index=accumulated.index)
        span = (start, end)

    calibration_data = accumulated[calibration_mask].dropna()
    years = calibration_data.index.year.nunique()
    if years < min_years:
        raise ValueError(
            f"Kalibrasyon dönemi {years} yıl — SPI için en az {min_years} yıl gerekir "
            f"(WMO önerisi). Daha uzun bir yağış serisi kullanın."
        )

    result = pd.Series(np.nan, index=accumulated.index, dtype="float64")
    zero_fraction: dict[int, float] = {}

    for month in range(1, 13):
        month_mask = accumulated.index.month == month
        fit_values = calibration_data[calibration_data.index.month == month].to_numpy()
        if fit_values.size < 10:
            continue

        # Thom (1958) karma dağılım: sıfırlar gamadan ayrı ele alınır.
        zeros = fit_values <= 0
        q = float(zeros.mean())
        zero_fraction[month] = q

        positive = fit_values[~zeros]
        if positive.size < 5 or np.allclose(positive, positive[0]):
            continue

        shape, loc, scale_param = gamma.fit(positive, floc=0)

        target = accumulated[month_mask]
        cdf = np.where(
            target.to_numpy() <= 0,
            q,
            q + (1 - q) * gamma.cdf(target.to_numpy(), shape, loc=loc, scale=scale_param),
        )
        # Kuantil fonksiyonu 0 ve 1'de sonsuza gider; uç değerleri kırp.
        cdf = np.clip(cdf, 1e-6, 1 - 1e-6)
        result[month_mask] = norm.ppf(cdf)

    return SPIResult(values=result, scale=scale, calibration=span, zero_fraction=zero_fraction)


def drought_events(spi_values: pd.Series, threshold: float = -1.0) -> pd.DataFrame:
    """Ardışık kurak ayları tek bir olay olarak gruplar.

    Kuraklık literatüründe olay bazlı analiz standarttır: 6 ay süren orta
    şiddetli bir kuraklık, tek aylık şiddetli bir sapmadan daha zararlıdır.
    """
    below = spi_values <= threshold
    groups = (below != below.shift()).cumsum()[below]

    events = []
    for _, group in spi_values[below].groupby(groups):
        events.append(
            {
                "başlangıç": group.index[0],
                "bitiş": group.index[-1],
                "süre_ay": len(group),
                "en_düşük_spi": float(group.min()),
                "şiddet": float(group.sum()),  # kümülatif açık
            }
        )
    return pd.DataFrame(events).sort_values("şiddet") if events else pd.DataFrame()
