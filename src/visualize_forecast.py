"""Adım 10 görselleri — SPI zaman serisi ve mekânsal anomali.

Renk kararları:
  - SPI ve anomali **çift kutuplu** (diverging) büyüklüklerdir: sıfırın iki
    yanı zıt anlam taşır (kurak / nemli). Bu yüzden iki hue ve NÖTR GRİ bir
    orta nokta kullanılır. Tek hue kullanmak, "normal"in nerede olduğunu
    gizlerdi; gökkuşağı kullanmak sıranın okunmasını engellerdi.
  - Kurak taraf sıcak kırmızı (risk haritasıyla aynı aile), nemli taraf mavi.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from .config import Config
from .fetch.common import resolve
from .grid import TargetGrid

# Çift kutuplu rampa: kurak (kırmızı) — nötr gri — nemli (mavi).
# Uçlar risk paletiyle ve dokümante mavi rampayla aynı aileden.
#
# Doğrulama (dataviz kontrolleri, zemin #fcfcfb):
#   kurak kolu  #e89286,#cc4234,#6b1c15  -> 4/4 PASS (tek hue, açık uç 2.30:1)
#   nemli kolu  #86b6ef,#2a78d6,#104281  -> 4/4 PASS (tek hue, açık uç 2.06:1)
#   iki uç ayrımı #cc4234 vs #2a78d6     -> CVD ΔE 24.4 (protan), normal 31.2
#
# Rampanın TAMAMINI tek-hue denetçisine vermek anlamsızdır: çift kutuplu bir
# ölçek tanımı gereği iki hue taşır ve nötr orta noktası tanımı gereği zemine
# yaklaşır — "burada bir şey olmuyor" demenin görsel karşılığı budur.
DIVERGING = ["#6b1c15", "#cc4234", "#e89286", "#f0efec", "#86b6ef", "#2a78d6", "#104281"]


def _diverging_cmap(masked_color: str) -> LinearSegmentedColormap:
    cmap = LinearSegmentedColormap.from_list("spi", DIVERGING)
    cmap.set_bad(masked_color)
    return cmap


def plot_spi_series(config: Config, results: dict, *, out_path: str | Path | None = None) -> Path:
    """SPI serilerini üst üste, kuraklık eşikleri işaretli olarak çizer."""
    viz = config["visualization"]
    scales = sorted(results)

    fig, axes = plt.subplots(
        len(scales), 1, figsize=(12, 2.6 * len(scales)), dpi=viz["dpi"], sharex=True
    )
    fig.patch.set_facecolor(viz["surface"])
    axes = np.atleast_1d(axes)

    for ax, scale in zip(axes, scales):
        series = results[scale].values.dropna()
        ax.set_facecolor(viz["surface"])

        # Kurak ve nemli dönemleri sıfır çizgisine göre ayrı doldur — işaret
        # bilgisi renkten önce ŞEKİLDEN okunsun.
        ax.fill_between(series.index, series.values, 0, where=series.values < 0,
                        color="#cc4234", alpha=0.85, linewidth=0, interpolate=True)
        ax.fill_between(series.index, series.values, 0, where=series.values >= 0,
                        color="#2a78d6", alpha=0.75, linewidth=0, interpolate=True)

        for threshold, style in ((-1.0, ":"), (-1.5, "--")):
            ax.axhline(threshold, color=viz["text_muted"], lw=0.9, ls=style)
        ax.axhline(0, color=viz["text_secondary"], lw=0.8)

        ax.text(0.005, 0.93, f"SPI-{scale}", transform=ax.transAxes,
                fontsize=11, color=viz["text_primary"], weight="bold", va="top")
        ax.text(0.005, 0.10, "− − −  şiddetli kurak (−1,5)", transform=ax.transAxes,
                fontsize=7.5, color=viz["text_muted"], va="bottom")

        ax.set_ylim(-3.2, 3.2)
        ax.set_ylabel("SPI", fontsize=9, color=viz["text_secondary"])
        ax.grid(axis="y", color=viz["gridline"], lw=0.7)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(viz["gridline"])
        ax.tick_params(colors=viz["text_muted"], labelsize=8.5)

    span = results[scales[0]].values.dropna()
    fig.suptitle(
        "Standartlaştırılmış Yağış İndeksi — Gediz Havzası",
        x=0.06, ha="left", fontsize=14, color=viz["text_primary"], weight="bold",
    )
    axes[0].set_title(
        f"TerraClimate, {span.index[0]:%Y} – {span.index[-1]:%Y} "
        f"({span.index.year.nunique()} yıl) · kırmızı = kurak, mavi = nemli",
        loc="left", fontsize=9.5, color=viz["text_muted"], pad=8,
    )
    axes[-1].set_xlabel("Yıl", fontsize=9, color=viz["text_secondary"])

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / "spi_series.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out


def plot_anomaly_map(
    config: Config, grid: TargetGrid, result, *, out_path: str | Path | None = None
) -> Path:
    """Mekânsal NDVI anomalisi haritası (z-skoru)."""
    viz = config["visualization"]
    cmap = _diverging_cmap(viz["masked_color"])

    left, bottom, right, top = grid.bounds
    extent = (left / 1000, right / 1000, bottom / 1000, top / 1000)

    fig, ax = plt.subplots(figsize=(11, 7.4), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])

    image = ax.imshow(
        np.ma.masked_invalid(result.z_score), cmap=cmap,
        norm=TwoSlopeNorm(vmin=-3, vcenter=0, vmax=3),
        extent=extent, interpolation="nearest",
    )
    ax.set_facecolor(viz["surface"])
    for spine in ax.spines.values():
        spine.set_color(viz["gridline"])
    ax.tick_params(colors=viz["text_muted"], labelsize=8)
    ax.set_xlabel("Doğu (km, UTM 35N)", fontsize=9, color=viz["text_secondary"])
    ax.set_ylabel("Kuzey (km, UTM 35N)", fontsize=9, color=viz["text_secondary"])

    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
    cbar.set_label(
        "Standartlaştırılmış anomali (z)\n← normalin altında      normalin üstünde →",
        fontsize=9, color=viz["text_secondary"],
    )
    cbar.ax.tick_params(colors=viz["text_muted"], labelsize=8)
    cbar.outline.set_visible(False)

    fig.suptitle(
        f"{result.year} Kurak Dönem {result.index_name.upper()} Anomalisi",
        x=0.06, ha="left", fontsize=14, color=viz["text_primary"], weight="bold",
    )
    ax.set_title(
        f"Taban çizgisi: {result.baseline_years} ({len(result.baseline_years)} yıl, "
        f"hedef yıl dışarıda) · {grid.resolution:g} m",
        loc="left", fontsize=9.5, color=viz["text_muted"], pad=10,
    )

    out = (
        Path(out_path)
        if out_path
        else resolve(config["paths"]["figures"]) / f"ndvi_anomaly_{result.year}.png"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out
