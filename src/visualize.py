"""Adım 5 — Risk haritası ve kriter paneli görselleştirmesi.

Renk kararları `config.yaml -> classification.colors` ve `visualization`
bloğundan gelir; burada hiçbir renk sabit değildir. Palet seçiminin gerekçesi
ve doğrulama sonuçları config içindeki yorumlarda.

Tasarım kuralları:
  - Risk sınıfları ordinal: tek hue, monoton açıklık — sıra renkte okunur.
  - Maskeli alanlar (yerleşim, su, veri boşluğu) nötr gri; risk sınıfı gibi
    görünmemeleri için paletin dışında bir renk kullanılır.
  - Eksen/ızgara geri planda kalır, veri öne çıkar.
  - Lejant her zaman var ve alan payını da taşır — renk tek başına bilgi
    taşımaz, etiket ve sayı ona eşlik eder.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # başsız ortam (CI, arka plan işleri)

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
from matplotlib.patches import Patch

from .config import Config
from .fetch.common import resolve
from .grid import TargetGrid


def _style(config: Config) -> dict:
    return config["visualization"]


def _extent_km(grid: TargetGrid) -> tuple[float, float, float, float]:
    """imshow için kilometre cinsinden kapsam (okunur eksen etiketleri)."""
    left, bottom, right, top = grid.bounds
    return (left / 1000, right / 1000, bottom / 1000, top / 1000)


def _clean_axes(ax, viz: dict) -> None:
    ax.set_facecolor(viz["surface"])
    for spine in ax.spines.values():
        spine.set_color(viz["gridline"])
        spine.set_linewidth(0.8)
    ax.tick_params(colors=viz["text_muted"], labelsize=8, length=3, width=0.8)


def _scale_bar(ax, grid: TargetGrid, viz: dict, length_km: float = 10.0) -> None:
    """Sol altta ölçek çubuğu, açık zemin kutusunun üstünde.

    Kutu şart: çubuk doğrudan haritanın üzerine çizildiğinde koyu risk
    sınıflarının üzerine düşüyor ve ne çubuk ne de etiketi okunuyordu.
    """
    left, right, bottom, top = _extent_km(grid)
    span_x, span_y = right - left, top - bottom

    pad_x, pad_y = span_x * 0.012, span_y * 0.02
    x0 = left + span_x * 0.035
    y0 = bottom + span_y * 0.055

    ax.add_patch(
        plt.Rectangle(
            (x0 - pad_x, y0 - pad_y),
            length_km + 2 * pad_x,
            span_y * 0.085,
            facecolor=viz["surface"], edgecolor="none", alpha=0.88, zorder=4,
        )
    )
    ax.plot([x0, x0 + length_km], [y0, y0],
            color=viz["text_primary"], lw=3.0, solid_capstyle="butt", zorder=5)
    ax.text(
        x0 + length_km / 2, y0 + span_y * 0.015, f"{length_km:g} km",
        ha="center", va="bottom", fontsize=8.5, color=viz["text_primary"], zorder=5,
    )


def _north_arrow(ax, grid: TargetGrid, viz: dict) -> None:
    """Sağ üstte kuzey oku, aynı gerekçeyle açık zemin kutusunun üstünde."""
    left, right, bottom, top = _extent_km(grid)
    span_x, span_y = right - left, top - bottom

    x = right - span_x * 0.045
    y_base = top - span_y * 0.115
    y_tip = top - span_y * 0.045

    ax.add_patch(
        plt.Rectangle(
            (x - span_x * 0.022, y_base - span_y * 0.045),
            span_x * 0.044, span_y * 0.125,
            facecolor=viz["surface"], edgecolor="none", alpha=0.88, zorder=4,
        )
    )
    ax.annotate(
        "", xy=(x, y_tip), xytext=(x, y_base),
        arrowprops=dict(arrowstyle="-|>", color=viz["text_primary"], lw=1.5), zorder=5,
    )
    ax.text(x, y_base - span_y * 0.012, "K", ha="center", va="top",
            fontsize=9.5, color=viz["text_primary"], weight="bold", zorder=5)


def plot_risk_map(
    config: Config,
    grid: TargetGrid,
    classes: np.ndarray,
    breaks: np.ndarray,
    *,
    out_path: str | Path | None = None,
) -> Path:
    """5 sınıflı risk haritasını stilize PNG olarak çizer."""
    viz = _style(config)
    cls_cfg = config["classification"]
    n = cls_cfg["n_classes"]
    labels = cls_cfg["labels"]
    colors = cls_cfg["colors"]

    cmap = ListedColormap(colors)
    display = np.ma.masked_where(classes == 0, classes)
    cmap.set_bad(viz["masked_color"])

    fig, ax = plt.subplots(figsize=(11, 7.6), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])

    ax.imshow(
        display, cmap=cmap, extent=_extent_km(grid),
        vmin=0.5, vmax=n + 0.5, interpolation="nearest",
    )
    _clean_axes(ax, viz)
    _scale_bar(ax, grid, viz)
    _north_arrow(ax, grid, viz)

    ax.set_xlabel("Doğu (km, UTM 35N)", fontsize=9, color=viz["text_secondary"])
    ax.set_ylabel("Kuzey (km, UTM 35N)", fontsize=9, color=viz["text_secondary"])

    total = int((classes > 0).sum())
    handles = []
    lower = 0.0
    for code in range(1, n + 1):
        share = 100 * int((classes == code).sum()) / total
        upper = float(breaks[code - 1])
        handles.append(
            Patch(facecolor=colors[code - 1],
                  label=f"{labels[code]}  ({lower:.2f}–{upper:.2f})   %{share:.1f}")
        )
        lower = upper
    handles.append(Patch(facecolor=viz["masked_color"], label="Maskeli (yerleşim / su)"))

    legend = ax.legend(
        handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1.0),
        frameon=False, fontsize=9, title="Kuraklık risk sınıfı\n(indeks aralığı, alan payı)",
        title_fontsize=9, alignment="left",
    )
    legend.get_title().set_color(viz["text_primary"])
    for text in legend.get_texts():
        text.set_color(viz["text_secondary"])

    fig.suptitle(
        "Tarımsal Kuraklık Risk Haritası — Gediz Havzası",
        x=0.06, ha="left", fontsize=15, color=viz["text_primary"], weight="bold",
    )
    years = config["periods"]["reference_years"]
    ax.set_title(
        f"AHP ağırlıklı çakıştırma, {len(config.criteria_order)} kriter · "
        f"{years[0]}–{years[-1]} kurak dönem · {grid.resolution:g} m · senaryo: {config.scenario}",
        loc="left", fontsize=9.5, color=viz["text_muted"], pad=10,
    )

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / f"risk_map_{config.scenario}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out


def plot_criteria_panel(
    config: Config,
    grid: TargetGrid,
    stack,
    result,
    *,
    out_path: str | Path | None = None,
) -> Path:
    """7 normalize kriteri küçük çoklu olarak yan yana gösterir.

    Hepsi aynı 0-1 skalasında ve aynı rampada çizilir; böylece paneller
    arasındaki koyuluk farkı doğrudan karşılaştırılabilir.
    """
    viz = _style(config)
    ramp = LinearSegmentedColormap.from_list("criterion", viz["criterion_ramp"])
    ramp.set_bad(viz["masked_color"])

    names = stack.names
    weights = result.weight_map
    ncols = 4
    nrows = int(np.ceil(len(names) / ncols))

    fig, axes = plt.subplots(nrows, ncols, figsize=(4.0 * ncols, 3.1 * nrows), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])
    axes = np.atleast_1d(axes).ravel()

    for ax, name, layer in zip(axes, names, stack.data):
        image = ax.imshow(
            np.ma.masked_invalid(layer), cmap=ramp, vmin=0, vmax=1,
            extent=_extent_km(grid), interpolation="nearest",
        )
        spec = config.criterion(name)
        ax.set_title(
            f"{spec['label']}\nağırlık {weights[name]:.3f}",
            fontsize=9, color=viz["text_primary"], loc="left", pad=6,
        )
        _clean_axes(ax, viz)
        ax.set_xticks([])
        ax.set_yticks([])

    for ax in axes[len(names):]:
        ax.axis("off")

    cbar = fig.colorbar(image, ax=axes[: len(names)].tolist(), fraction=0.02, pad=0.02)
    cbar.set_label("Kuraklık risk skoru (0 = düşük, 1 = yüksek)", fontsize=9, color=viz["text_secondary"])
    cbar.ax.tick_params(colors=viz["text_muted"], labelsize=8)
    cbar.outline.set_visible(False)

    fig.suptitle(
        "Normalize Edilmiş Kriter Katmanları",
        x=0.06, y=0.99, ha="left", fontsize=14, color=viz["text_primary"], weight="bold",
    )

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / f"criteria_panel_{config.scenario}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out


def plot_risk_histogram(
    config: Config,
    risk: np.ndarray,
    breaks: np.ndarray,
    *,
    out_path: str | Path | None = None,
) -> Path:
    """Risk indeksinin dağılımı ve sınıf sınırlarının nereye düştüğü.

    Sınıflandırmanın veriye uyup uymadığını gösteren en dürüst grafik budur:
    sınırlar dağılımın doğal boşluklarına denk geliyorsa Jenks işini yapmıştır.
    """
    viz = _style(config)
    cls_cfg = config["classification"]
    colors = cls_cfg["colors"]
    values = risk[np.isfinite(risk)]

    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])
    ax.set_facecolor(viz["surface"])

    counts, edges = np.histogram(values, bins=120)
    centers = (edges[:-1] + edges[1:]) / 2
    bin_class = np.clip(np.digitize(centers, breaks[:-1], right=True), 0, len(colors) - 1)

    # Sürekli bir dağılımda kutular bitişik olmalı: aralık bırakmak, veride
    # olmayan boşluklar varmış gibi görünen yapay çizgiler üretir.
    ax.bar(
        centers, counts, width=(edges[1] - edges[0]),
        color=[colors[i] for i in bin_class], linewidth=0,
    )

    headroom = counts.max() * 1.13
    ax.set_ylim(0, headroom)
    for edge in breaks[:-1]:
        ax.axvline(edge, color=viz["text_muted"], lw=0.9, ls="--", alpha=0.8, zorder=2)
        # Etiketler çubukların üstünde değil, üstteki boşlukta dursun.
        ax.text(
            edge, headroom * 0.985, f"{edge:.3f}",
            fontsize=8, color=viz["text_muted"], va="top", ha="center",
            bbox=dict(facecolor=viz["surface"], edgecolor="none", pad=1.5),
        )

    ax.set_xlabel("AHP kuraklık risk indeksi", fontsize=9.5, color=viz["text_secondary"])
    ax.set_ylabel("Piksel sayısı", fontsize=9.5, color=viz["text_secondary"])
    ax.set_title(
        f"Risk indeksi dağılımı ve {cls_cfg['method'].capitalize()} sınıf sınırları",
        loc="left", fontsize=12, color=viz["text_primary"], weight="bold", pad=10,
    )
    ax.grid(axis="y", color=viz["gridline"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(viz["gridline"])
    ax.tick_params(colors=viz["text_muted"], labelsize=8.5)

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / f"risk_histogram_{config.scenario}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    return out
