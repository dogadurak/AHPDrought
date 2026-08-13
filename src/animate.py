"""Adım 6 — NDVI zaman serisi görselleştirmesi.

İki çıktı:
  1. 12 aylık NDVI kompozitinden animasyon (GIF) — mevsimsel bitki örtüsü
     döngüsünün mekânsal görünümü.
  2. Arazi örtüsü sınıflarına göre seçilmiş örnek parsellerin yıl içi NDVI
     eğrisi — "yaprağın ne zaman sarardığını" sayıyla gösteren grafik.

Tüm kareler AYNI renk ölçeğini kullanır. Kare başına ölçeği yeniden hesaplamak
animasyonu görsel olarak canlandırır ama tamamen yanıltıcıdır: aylar arasındaki
gerçek fark kaybolur, her ay kendi içinde normalize edildiği için hepsi
birbirine benzer görünür.
"""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from .config import Config, load_json
from .fetch.common import interim_path, resolve
from .grid import TargetGrid, read_grid_aligned

MONTH_NAMES_TR = [
    "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


def _ndvi_cmap(config: Config) -> LinearSegmentedColormap:
    viz = config["visualization"]
    cmap = LinearSegmentedColormap.from_list("ndvi", viz["ndvi_ramp"])
    cmap.set_bad(viz["masked_color"])
    return cmap


def monthly_paths(config: Config) -> list[tuple[int, Path]]:
    """Animasyon yılının aylık NDVI dosyalarını (ay, yol) olarak sıralar."""
    ts = config["periods"]["timeseries"]
    year = ts["year"]
    found = []
    for month in ts["months"]:
        path = interim_path(config, "ndvi_monthly", f"ndvi_{year}_{month:02d}.tif")
        if path.exists():
            found.append((month, path))
    if not found:
        raise FileNotFoundError(
            f"{year} yılı için aylık NDVI kompoziti yok. "
            "Önce `python -m scripts.step02_fetch_data --only ndvi-series` çalıştırın."
        )
    return found


def _read(path: Path, grid: TargetGrid, config: Config) -> np.ndarray:
    array = read_grid_aligned(path, grid).astype("float32")
    return np.where(array == np.float32(config.nodata), np.nan, array)


def make_ndvi_animation(
    config: Config,
    grid: TargetGrid,
    *,
    out_path: str | Path | None = None,
    fps: float = 1.6,
    downsample: int = 3,
) -> Path:
    """12 aylık NDVI kompozitinden GIF animasyonu üretir.

    Args:
        downsample: Kareleri her N pikselde bir örnekler. 30 m tam çözünürlükte
            bir GIF onlarca MB olur ve README'ye gömülemez; 90 m'de mevsimsel
            desen tamamen okunur kalır.
    """
    import imageio.v2 as imageio

    viz = config["visualization"]
    vmin, vmax = viz["ndvi_display_range"]
    cmap = _ndvi_cmap(config)
    year = config["periods"]["timeseries"]["year"]

    frames = []
    for month, path in monthly_paths(config):
        array = _read(path, grid, config)[::downsample, ::downsample]

        fig, ax = plt.subplots(figsize=(8.4, 5.6), dpi=110)
        fig.patch.set_facecolor(viz["surface"])
        image = ax.imshow(np.ma.masked_invalid(array), cmap=cmap, vmin=vmin, vmax=vmax,
                          interpolation="nearest")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        ax.set_title(
            f"{MONTH_NAMES_TR[month - 1]} {year}",
            loc="left", fontsize=15, color=viz["text_primary"], weight="bold", pad=8,
        )
        ax.text(
            0.0, -0.04, f"NDVI medyan kompoziti · Gediz Havzası · {grid.resolution * downsample:g} m",
            transform=ax.transAxes, fontsize=9, color=viz["text_muted"], va="top",
        )

        cbar = fig.colorbar(image, ax=ax, fraction=0.032, pad=0.02)
        cbar.set_label("NDVI", fontsize=9, color=viz["text_secondary"])
        cbar.ax.tick_params(colors=viz["text_muted"], labelsize=8)
        cbar.outline.set_visible(False)

        frame_path = resolve(config["paths"]["figures"]) / "_frames" / f"ndvi_{year}_{month:02d}.png"
        frame_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(frame_path, bbox_inches="tight", facecolor=viz["surface"])
        plt.close(fig)
        frames.append(frame_path)

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / f"ndvi_animation_{year}.gif"
    out.parent.mkdir(parents=True, exist_ok=True)

    images = [imageio.imread(f) for f in frames]
    # Kareler farklı bbox kırpmalarıyla birkaç piksel farklı çıkabilir; GIF
    # tüm karelerin aynı boyutta olmasını ister.
    shape = min((im.shape[:2] for im in images), key=lambda s: s[0] * s[1])
    images = [im[: shape[0], : shape[1]] for im in images]

    imageio.mimsave(out, images, duration=1000 / fps, loop=0)
    print(f"  animasyon: {len(images)} kare, {out.stat().st_size / 1e6:.1f} MB")
    return out


# --- Örnek parsel eğrileri ---------------------------------------------------


def sample_parcels(
    config: Config, grid: TargetGrid, *, per_class: int = 40, window: int = 3, seed: int = 0
) -> dict[str, list[tuple[int, int]]]:
    """Baskın arazi örtüsü sınıflarından temsili piksel konumları seçer.

    Kenarlardan `window` kadar içeride kalan, sınıfı saf olan konumlar seçilir;
    böylece 3x3 pencere ortalaması karışık piksel içermez.
    """
    from scipy.ndimage import uniform_filter

    codes = read_grid_aligned(interim_path(config, "landcover.tif"), grid)
    lookup = load_json(config["data_sources"]["landcover"]["lookup_file"])["classes"]
    rng = np.random.default_rng(seed)

    # İlgi sınıfları: tarım, orman, mera — havzanın %95'i.
    wanted = {"40": "Tarım alanı", "10": "Orman", "30": "Mera"}
    half = window // 2
    selected: dict[str, list[tuple[int, int]]] = {}

    for code_str, label in wanted.items():
        code = int(code_str)
        pure = uniform_filter((codes == code).astype("float32"), size=window) > 0.999
        pure[:half + 1, :] = pure[-half - 1:, :] = False
        pure[:, :half + 1] = pure[:, -half - 1:] = False

        rows, cols = np.nonzero(pure)
        if rows.size == 0:
            print(f"      {label}: saf parsel bulunamadı, atlandı")
            continue
        idx = rng.choice(rows.size, size=min(per_class, rows.size), replace=False)
        selected[label] = list(zip(rows[idx].tolist(), cols[idx].tolist()))
        print(f"      {label} ({lookup[code_str]['name']}): {len(idx)} parsel")

    return selected


def plot_parcel_curves(
    config: Config, grid: TargetGrid, *, window: int = 3, out_path: str | Path | None = None
) -> Path:
    """Arazi örtüsü sınıflarına göre yıl içi ortalama NDVI eğrisi."""
    viz = config["visualization"]
    year = config["periods"]["timeseries"]["year"]
    parcels = sample_parcels(config, grid, window=window)
    half = window // 2

    months, series = [], {label: [] for label in parcels}
    for month, path in monthly_paths(config):
        array = _read(path, grid, config)
        months.append(month)
        for label, points in parcels.items():
            values = [
                np.nanmean(array[r - half:r + half + 1, c - half:c + half + 1]) for r, c in points
            ]
            series[label].append(float(np.nanmean(values)))

    # Dokümante kategorik paletin ilk üç yuvası (tüm-çift kontrollerini geçer).
    palette = {"Tarım alanı": "#2a78d6", "Orman": "#eb6834", "Mera": "#1baf7a"}

    fig, ax = plt.subplots(figsize=(9.5, 5.0), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])
    ax.set_facecolor(viz["surface"])

    for label, values in series.items():
        color = palette.get(label, "#2a78d6")
        ax.plot(months, values, color=color, lw=2.0, marker="o", markersize=5,
                markeredgecolor=viz["surface"], markeredgewidth=1.4, label=label, zorder=3)
        # Doğrudan etiket: kimlik yalnızca renkte kalmasın.
        ax.annotate(
            label, xy=(months[-1], values[-1]), xytext=(6, 0), textcoords="offset points",
            color=color, fontsize=9.5, va="center", weight="bold",
        )

    dry = config["periods"]["dry_season"]
    ax.axvspan(dry["start_month"] - 0.5, dry["end_month"] + 0.5,
               color=viz["gridline"], alpha=0.55, zorder=0)
    ax.text(
        (dry["start_month"] + dry["end_month"]) / 2, ax.get_ylim()[1],
        "kurak dönem", ha="center", va="bottom", fontsize=8.5, color=viz["text_muted"],
    )

    ax.set_xticks(range(1, 13))
    ax.set_xticklabels([m[:3] for m in MONTH_NAMES_TR], fontsize=8.5)
    ax.set_xlim(0.5, 13.6)
    ax.set_ylabel("NDVI (parsel ortalaması)", fontsize=9.5, color=viz["text_secondary"])
    ax.set_title(
        f"Arazi Örtüsüne Göre Yıl İçi NDVI Seyri — {year}",
        loc="left", fontsize=13, color=viz["text_primary"], weight="bold", pad=10,
    )
    ax.grid(axis="y", color=viz["gridline"], lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(viz["gridline"])
    ax.tick_params(colors=viz["text_muted"], labelsize=8.5)
    ax.legend(frameon=False, fontsize=9, loc="lower left", ncols=3)

    out = Path(out_path) if out_path else resolve(config["paths"]["figures"]) / f"ndvi_parcel_curves_{year}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)

    _write_curve_table(config, months, series, out.with_suffix(".md"))
    return out


def _write_curve_table(config: Config, months, series, out: Path) -> None:
    """Grafiğin sayısal karşılığı — renk okunamadığında da erişilebilir olsun."""
    header = "| Ay | " + " | ".join(series) + " |"
    divider = "|---" * (len(series) + 1) + "|"
    rows = [
        f"| {MONTH_NAMES_TR[m - 1]} | " + " | ".join(f"{series[k][i]:.3f}" for k in series) + " |"
        for i, m in enumerate(months)
    ]
    out.write_text(
        f"# Arazi örtüsüne göre aylık ortalama NDVI — {config['periods']['timeseries']['year']}\n\n"
        + "\n".join([header, divider, *rows])
        + "\n",
        encoding="utf-8",
    )
