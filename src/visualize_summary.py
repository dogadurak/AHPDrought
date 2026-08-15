"""Özet sayfası için sentez grafikleri.

Bu grafikler tek tek analizleri değil, **projenin argümanını** taşır. Üçü de
projenin doğrulanmış paletini kullanır (bkz. config.yaml yorumları):

  kırmızı ailesi  -> olumsuz / stres
  mavi ailesi     -> olumlu / doğrulanmış
  nötr gri        -> referans, taban çizgisi

Kural: sıra anlam taşıyorsa tek hue üzerinde monoton açıklık; iki kutup varsa
iki hue + nötr orta. Gökkuşağı yok.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from .config import Config
from .fetch.common import resolve

FAIL = "#cc4234"
PASS = "#2a78d6"
HOLD = "#eda100"
NEUTRAL = "#c3c2b7"


def _style(config: Config) -> dict:
    return config["visualization"]


def _finish(ax, viz: dict) -> None:
    ax.set_facecolor(viz["surface"])
    ax.grid(axis="x", color=viz["gridline"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(viz["gridline"])
    ax.tick_params(colors=viz["text_muted"], labelsize=9)


def plot_forecast_skill(config: Config, *, out_path: str | Path | None = None) -> Path:
    """Sorunun kurulumu sonucu nasıl belirledi — projenin başlık bulgusu.

    Yatay çubuk, sıfırın iki yanında: negatif beceri "referanstan kötü" demek,
    yani sıfır anlamlı bir eşik. Bu yüzden çift kutuplu renk kullanılıyor.
    """
    viz = _style(config)
    rows = [
        ("Nisan toprak nemi → yaz stresi", 0.445, "fiziksel soru"),
        ("Nisan yağışı → yaz stresi", 0.379, "fiziksel soru"),
        ("Sönümlü kalıcılık, 1 ay", 0.395, "kısa ufuk"),
        ("Sönümlü kalıcılık, 3 ay", -0.001, "mekanik soru"),
        ("Kalıcılık, 3 ay", -0.964, "mekanik soru"),
        ("Kalıcılık, 6 ay", -1.076, "mekanik soru"),
    ]
    labels = [r[0] for r in rows]
    values = [r[1] for r in rows]
    colors = [PASS if v > 0.05 else (FAIL if v < -0.05 else NEUTRAL) for v in values]

    fig, ax = plt.subplots(figsize=(9.6, 4.4), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])

    y = np.arange(len(rows))[::-1]
    ax.barh(y, values, height=0.62, color=colors, linewidth=0)
    ax.axvline(0, color=viz["text_secondary"], lw=1.1)

    for yi, (label, value, _) in zip(y, rows):
        offset = 0.03 if value >= 0 else -0.03
        ax.text(value + offset, yi, f"{value:+.3f}",
                va="center", ha="left" if value >= 0 else "right",
                fontsize=9.5, color=viz["text_primary"], fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9.5, color=viz["text_primary"])
    ax.set_xlim(-1.35, 0.72)
    ax.set_xlabel("Beceri skoru — iklimatolojiye karşı  (0 = referanstan farksız)",
                  fontsize=9.5, color=viz["text_secondary"])
    ax.set_title(
        "Aynı veri, aynı 3 aylık ufuk — sonucu sorunun kurulumu belirledi",
        loc="left", fontsize=13, color=viz["text_primary"], fontweight="bold", pad=12,
    )
    _finish(ax, viz)
    # Yön etiketleri eksenin BOŞ bölgelerine konur: üst-sol (negatif taraf,
    # oradaki çubuklar pozitif) ve alt-sağ (pozitif taraf, oradaki çubuklar
    # negatif). Veri koordinatı yerine eksen kesri kullanmak, etiketi eksen
    # dışına taşırıp başlığın üstüne bindiriyordu.
    ax.text(0.02, 0.955, "← referanstan KÖTÜ", transform=ax.transAxes,
            fontsize=8.5, color=FAIL, fontweight="bold", va="top")
    ax.text(0.98, 0.045, "gerçek beceri →", transform=ax.transAxes,
            fontsize=8.5, color=PASS, fontweight="bold", ha="right", va="bottom")

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / "summary_forecast_skill.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out


def plot_validation_attempts(config: Config, *, out_path: str | Path | None = None) -> Path:
    """Sınama beş kez daha adil kuruldu; ilişki hep sıfır civarında kaldı."""
    viz = _style(config)
    # Kurak yıl sayıları etiketleme ölçütüne bağlı: ilk iki satır yaz SPI'ı
    # kullanıyordu (9 yılda 1 kurak yıl), sonrakiler ilkbahar toprak nemi
    # (6 kurak yıl). Ölçütün kendisi de bir bulgu — bkz. operational.py.
    rows = [
        ("Sentinel-2 · tek yıl · z-skoru", 1, -0.096),
        ("Sentinel-2 · 9 yıl · z-skoru · havza", 1, -0.042),
        ("Sentinel-2 · 9 yıl · ham fark · tarım", 6, -0.057),
        ("Sentinel-2 · yağmura bağlı tarım", 6, -0.067),
        ("Landsat · 27 yıl · tarım", 7, -0.021),
        ("MODIS ET/PET · 25 yıl · tarım", 3, +0.050),
    ]
    labels = [r[0] for r in rows]
    dry = [r[1] for r in rows]
    rho = [r[2] for r in rows]

    fig, ax = plt.subplots(figsize=(9.6, 4.2), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])

    y = np.arange(len(rows))[::-1]
    # Anlamlılık eşiği bandı: |rho| < 0.10 pratikte sıfırdan ayırt edilemez
    ax.axvspan(-0.10, 0.10, color=viz["gridline"], alpha=0.75, zorder=0)
    ax.axvline(0, color=viz["text_secondary"], lw=1.0, zorder=1)

    ax.hlines(y, 0, rho, color=NEUTRAL, lw=1.6, zorder=2)
    ax.scatter(rho, y, s=118, color=FAIL, edgecolor=viz["surface"],
               linewidth=1.6, zorder=3)

    for yi, value, n in zip(y, rho, dry):
        ax.text(value - 0.012, yi + 0.30, f"{value:+.3f}", fontsize=9,
                color=viz["text_primary"], fontweight="bold", ha="center")
        ax.text(0.335, yi, f"{n} kurak yıl", fontsize=8.5,
                color=viz["text_muted"], va="center", ha="right")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9.5, color=viz["text_primary"])
    ax.set_xlim(-0.36, 0.36)
    ax.set_xlabel("Risk indeksi ile gözlenen etki arasında Spearman ρ (kurak yıllar)",
                  fontsize=9.5, color=viz["text_secondary"])
    ax.set_title(
        "Sınama beş kez daha adil kuruldu — ilişki hep sıfır bandında kaldı",
        loc="left", fontsize=13, color=viz["text_primary"], fontweight="bold", pad=12,
    )
    _finish(ax, viz)
    # Açıklama için eksenin altında BOŞ bant açılır. Veri alanına yazınca son
    # satırla, eksen dışına yazınca x etiketiyle çakışıyordu — yer açmak,
    # yerleştirmeyi zorlamaktan daha sağlam.
    ax.set_ylim(-1.15, len(rows) - 0.45)
    ax.text(0, -0.95, "gri bant: |ρ| < 0,10 — pratikte sıfırdan ayırt edilemez",
            fontsize=8.5, color=viz["text_muted"], ha="center", va="center")

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / "summary_validation.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out


def plot_irrigation_masking(config: Config, *, out_path: str | Path | None = None) -> Path:
    """Sulama, NDVI'daki kuraklık sinyalini maskeliyor — projenin en net bulgusu."""
    viz = _style(config)
    years = ["2024\nkurak", "2025\nkurak", "2023\nyağışlı"]
    near = [-0.0043, -0.0151, +0.0146]
    far = [-0.0428, -0.0315, +0.0177]

    fig, ax = plt.subplots(figsize=(8.4, 4.6), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])

    x = np.arange(len(years))
    width = 0.34
    ax.bar(x - width / 2, near, width, label="kanala < 2 km (sulanan)",
           color=PASS, linewidth=0)
    ax.bar(x + width / 2, far, width, label="kanaldan > 10 km (yağmura bağlı)",
           color=FAIL, linewidth=0)
    ax.axhline(0, color=viz["text_secondary"], lw=1.0)

    for xi, (a, b) in enumerate(zip(near, far)):
        for offset, value in ((-width / 2, a), (width / 2, b)):
            va = "top" if value < 0 else "bottom"
            pad = -0.0018 if value < 0 else 0.0018
            ax.text(xi + offset, value + pad, f"{value:+.4f}", ha="center", va=va,
                    fontsize=8.5, color=viz["text_primary"], fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(years, fontsize=10, color=viz["text_primary"])
    ax.set_ylabel("Tarım alanı NDVI anomalisi", fontsize=9.5, color=viz["text_secondary"])
    # En derin çubuğun etiketi için altta yer bırakılır; yoksa eksen dışına
    # taşıp efsanenin üstüne biniyordu.
    ax.set_ylim(-0.052, 0.026)
    ax.set_title(
        "Sulama, kuraklık sinyalini maskeliyor",
        loc="left", fontsize=13, color=viz["text_primary"], fontweight="bold", pad=26,
    )
    ax.text(0, 1.015, "Fark yalnızca stres varken ortaya çıkıyor — yağışlı yılda iki grup aynı",
            transform=ax.transAxes, fontsize=9.5, color=viz["text_muted"], va="bottom")

    ax.set_facecolor(viz["surface"])
    ax.grid(axis="y", color=viz["gridline"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(viz["gridline"])
    ax.tick_params(colors=viz["text_muted"], labelsize=9)
    # Sol üst, 2024/2025 çubukları negatif olduğu için boş kalan tek bölge.
    ax.legend(frameon=False, fontsize=9, loc="upper left")

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / "summary_irrigation.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out


def build_all(config: Config) -> list[Path]:
    return [
        plot_forecast_skill(config),
        plot_validation_attempts(config),
        plot_irrigation_masking(config),
    ]
