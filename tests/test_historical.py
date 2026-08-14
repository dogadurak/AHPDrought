"""Tarihsel sınama modülünün testleri (Adım 13).

En kritik olan, iki dönemin karıştırılmaması: Landsat NDVI'ı Sentinel-2
NDVI'ından sistematik olarak farklıdır (sensör + 35 yıllık arazi kullanımı
değişimi). Taban çizgisine yanlışlıkla Sentinel yılı karışsa, anomali gerçek
bir kuraklık gibi görünen sahte bir sapma üretirdi.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.historical import MIN_BASELINE_YEARS, _verdict, pooled_by_class, severity_index


def row(year: int, spi: float, is_dry: bool, rho: float, by_class=None) -> dict:
    return {
        "year": year, "spi12": spi, "is_dry": is_dry, "rho": rho,
        "mean_anomaly": -0.01,
        "by_class": by_class or [(c, -0.01 * c, 1000) for c in range(1, 6)],
        "monotone": True,
    }


def result_from(rows: list[dict], threshold: float = -1.0) -> dict:
    dry = [r for r in rows if r["is_dry"]]
    normal = [r for r in rows if not r["is_dry"]]
    return {
        "rows": rows, "dry": dry, "normal": normal,
        "dry_rho": float(np.mean([r["rho"] for r in dry])) if dry else float("nan"),
        "normal_rho": float(np.mean([r["rho"] for r in normal])) if normal else float("nan"),
        "threshold": threshold, "landcover_code": 40,
    }


# --- Kuraklık şiddeti --------------------------------------------------------


def test_severity_uses_dry_season_months():
    index = pd.date_range("1985-01", periods=10 * 12, freq="MS")
    series = pd.Series(0.0, index=index)
    mask = (series.index.year == 1990) & (series.index.month.isin([7, 8, 9]))
    series[mask] = -2.5

    severity = severity_index(series, [1989, 1990, 1991])
    assert severity[1990] == pytest.approx(-2.5)
    assert severity[1989] == pytest.approx(0.0)


def test_severity_reports_nan_for_missing_years():
    index = pd.date_range("1985-01", periods=24, freq="MS")
    severity = severity_index(pd.Series(0.0, index=index), [1985, 2099])
    assert not np.isfinite(severity[2099])


# --- Havuzlama ---------------------------------------------------------------


def test_pooling_is_weighted_by_pixel_count():
    a = row(1990, -2.5, True, -0.3, by_class=[(1, -1.0, 10)])
    b = row(2007, -2.6, True, -0.3, by_class=[(1, 0.0, 990)])
    pooled = dict(pooled_by_class(result_from([a, b]), dry_only=True))
    assert pooled[1] == pytest.approx(-0.01)


def test_pooling_all_years_includes_normal_years():
    dry = row(1990, -2.5, True, -0.3, by_class=[(1, -1.0, 100)])
    normal = row(1998, 0.2, False, -0.05, by_class=[(1, 1.0, 100)])
    result = result_from([dry, normal])

    assert dict(pooled_by_class(result, dry_only=True))[1] == pytest.approx(-1.0)
    assert dict(pooled_by_class(result, dry_only=False))[1] == pytest.approx(0.0)


# --- Hüküm -------------------------------------------------------------------


def test_verdict_needs_enough_dry_years():
    rows = [row(1990, -2.5, True, -0.4)] + [row(y, 0.2, False, -0.05) for y in range(1995, 2005)]
    assert "KARAR VERİLEMEZ" in _verdict(result_from(rows), 3, 0.10)


def test_verdict_supports_when_dry_years_are_clearly_stronger():
    dry = [row(y, -2.0, True, -0.40) for y in (1989, 1990, 2007)]
    normal = [row(y, 0.3, False, -0.05) for y in (1995, 1998, 2003)]
    verdict = _verdict(result_from(dry + normal), 3, 0.10)

    assert "DESTEKLENDİ" in verdict
    assert "DESTEKLENMEDİ" not in verdict


def test_verdict_rejects_near_zero_effect():
    dry = [row(y, -2.0, True, -0.04) for y in (1989, 1990, 2007)]
    normal = [row(y, 0.3, False, -0.02) for y in (1995, 1998)]
    verdict = _verdict(result_from(dry + normal), 3, 0.10)

    assert "DESTEKLENMEDİ" in verdict
    assert "fiilen sıfır" in verdict


def test_verdict_rejects_when_dry_and_normal_are_similar():
    dry = [row(y, -2.0, True, -0.30) for y in (1989, 1990, 2007)]
    normal = [row(y, 0.3, False, -0.28) for y in (1995, 1998)]
    verdict = _verdict(result_from(dry + normal), 3, 0.10)

    assert "DESTEKLENMEDİ" in verdict
    assert "ayırt etmiyor" in verdict


def test_verdict_needs_normal_years_for_comparison():
    dry = [row(y, -2.0, True, -0.40) for y in (1989, 1990, 2007)]
    assert "KARAR VERİLEMEZ" in _verdict(result_from(dry), 3, 0.10)


# --- Dönem ayrımı ------------------------------------------------------------


def test_baseline_minimum_is_documented():
    """Landsat taban çizgisi için en az 10 yıl — az yılla anomali gürültülü olur."""
    assert MIN_BASELINE_YEARS >= 10


def test_landsat_config_uses_a_single_sensor():
    """Çoklu sensör NDVI'da sistematik fark yaratır; tek platforma bağlı kalınmalı."""
    from src.config import load_config

    cfg = load_config()["data_sources"]["landsat"]
    assert cfg["platform"] == "landsat-5"
    # Landsat 5'in fiilen çalıştığı dönem
    assert cfg["start_year"] >= 1984
    assert cfg["end_year"] <= 2012


def test_landsat_qa_band_is_resampled_categorically():
    """QA_PIXEL bit alanıdır; ortalaması alınırsa bitler anlamsızlaşır."""
    from src.config import load_config

    cfg = load_config()["data_sources"]["landsat"]
    assert cfg["resampling"][cfg["bands"]["qa"]] in ("nearest", "mode")


def test_landsat_covers_the_known_droughts():
    """1989-91 ve 2007 kuraklıkları dönemin içinde olmalı."""
    from src.config import load_config

    cfg = load_config()["data_sources"]["landsat"]
    for year in (1989, 1990, 1991, 2001, 2007, 2008):
        assert cfg["start_year"] <= year <= cfg["end_year"], f"{year} kapsam dışı"
