"""Dashboard'ların okuduğu tek veri dosyasını üretir.

Amaç: hiçbir sayı arayüz koduna elle yazılmasın. React (`web-app/`) ve
Streamlit (`dashboard/`) aynı JSON'u okur; JSON `config.yaml` ile
`outputs/reports/` altındaki üretilmiş raporlardan türetilir. Böylece
analiz yeniden çalıştığında arayüzdeki sayılar da güncellenir ve iki
arayüz asla birbirinden sapmaz.

Kullanım:
    python -m scripts.export_web_data
    python -m scripts.export_web_data --scenario flat_riskier
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from src.ahp import solve_from_config
from src.config import PROJECT_ROOT, load_config

WEB_DIR = PROJECT_ROOT / "web-app" / "public" / "data"
WEB_DATA = WEB_DIR / "summary.json"
REPORTS = PROJECT_ROOT / "outputs" / "reports"
PROCESSED = PROJECT_ROOT / "data" / "processed"


class ExportError(RuntimeError):
    """Rapor beklenen biçimde değilse fırlatılır."""


# --- rapor ayrıştırma --------------------------------------------------------
#
# Raporlar `src/` tarafından sabit bir hizalı-kolon biçiminde yazılıyor.
# Ayrıştırma kasten katı: biçim değişirse sessizce yanlış sayı üretmek
# yerine hata vermesi gerekiyor.


def _read_report(name: str) -> str:
    path = REPORTS / name
    if not path.exists():
        raise ExportError(
            f"{path.relative_to(PROJECT_ROOT)} yok — önce ilgili adımı çalıştırın."
        )
    return path.read_text(encoding="utf-8")


def _parse_effective_contribution(text: str) -> dict[str, float]:
    """"Nominal ağırlık ve efektif katkı" bloğundan efektif katkıları alır."""
    # satır biçimi:  precipitation   0.2135   0.00 - 1.00   %24.3
    pattern = re.compile(
        r"^(\w+)\s+([\d.]+)\s+([\d.]+)\s*-\s*([\d.]+)\s+%([\d.]+)\s*$",
        re.MULTILINE,
    )
    out: dict[str, float] = {}
    for name, _weight, lo, hi, eff in pattern.findall(text):
        out[name] = {
            "effective_pct": float(eff),
            "used_range": [float(lo), float(hi)],
        }
    if not out:
        raise ExportError("AHP raporunda efektif katkı bloğu bulunamadı.")
    return out


def _parse_risk_classes(text: str) -> list[dict[str, Any]]:
    """"Risk sınıfları" bloğundan sınıf başına piksel/pay/alan alır."""
    # satır biçimi:  1  Çok düşük  0.4163  669,824  %13.0  602.8
    pattern = re.compile(
        r"^([1-9])\s+(.+?)\s{2,}([\d.]+)\s+([\d,]+)\s+%([\d.]+)\s+([\d,.]+)\s*$",
        re.MULTILINE,
    )
    rows = [
        {
            "class": int(idx),
            "label": label.strip(),
            "upper_bound": float(upper),
            "pixels": int(px.replace(",", "")),
            "share_pct": float(share),
            "area_km2": float(area.replace(",", "")),
        }
        for idx, label, upper, px, share, area in pattern.findall(text)
    ]
    if not rows:
        raise ExportError("AHP raporunda risk sınıfı bloğu bulunamadı.")
    return rows


def _parse_masked(text: str) -> dict[str, float] | None:
    m = re.search(r"Maskeli.*?:\s*([\d,]+)\s*piksel,\s*([\d.]+)\s*km", text)
    if not m:
        return None
    return {
        "pixels": int(m.group(1).replace(",", "")),
        "area_km2": float(m.group(2)),
    }


def _tr_float(token: str) -> float:
    """"−0,0428" / "**+0,0146**" gibi Türkçe biçimli sayıyı float'a çevirir.

    Raporlar insan okuması için yazıldığından Unicode eksi (U+2212), ondalık
    virgül ve markdown kalın işaretleri içerir.
    """
    cleaned = (
        token.replace("*", "")
        .replace("−", "-")
        .replace("–", "-")
        .replace(",", ".")
        .strip()
    )
    return float(cleaned)


def _parse_irrigation_effect(text: str) -> list[dict[str, Any]]:
    """Sulama mesafesine göre kurak yıl NDVI anomalisi tablosunu alır.

    Projenin en güçlü doğrulaması bu tablo. Rapor biçimi değişirse boş liste
    döner ve dashboard bölümü kendini gizler — yanlış sayı göstermez.
    """
    # | 2024 (kurak) | −0,0043 | **−0,0428** | 10× |
    pattern = re.compile(
        r"^\|\s*(\d{4})\s*\(([^)]+)\)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
        re.MULTILINE,
    )
    rows: list[dict[str, Any]] = []
    for year, condition, near, far in pattern.findall(text):
        try:
            rows.append(
                {
                    "year": int(year),
                    "condition": condition.strip(),
                    "dry": condition.strip().lower().startswith("kurak"),
                    "near_canal": _tr_float(near),
                    "far_from_canal": _tr_float(far),
                }
            )
        except ValueError:
            continue
    return rows


YEARLY_SECTION = "### Yalnızca tarım alanı"


def _parse_yearly_operational(text: str) -> list[dict[str, Any]]:
    """Yıl bazında SPI, ortalama anomali ve risk-anomali korelasyonu.

    Rapor aynı biçimde dört tablo içeriyor (z-skoru, ham fark, yalnızca
    tarım, yağmura bağlı tarım). En adil kurgu olan "yalnızca tarım alanı"
    bölümü seçilir; hepsini birden almak yılları dört kez tekrarlardı.
    """
    start = text.find(YEARLY_SECTION)
    if start != -1:
        nxt = text.find("\n### ", start + 1)
        text = text[start : nxt if nxt != -1 else len(text)]
    # 2017    -0.73     KURAK          0.010          -0.0955     hayır
    pattern = re.compile(
        r"^(\d{4})\s+(-?[\d.]+)\s+(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(\S+)\s*$",
        re.MULTILINE,
    )
    return [
        {
            "year": int(year),
            "spi": float(spi),
            "dry": state.upper() == "KURAK",
            "mean_anomaly": float(anom),
            "risk_anomaly_rho": float(rho),
            "monotonic": monotonic.lower() in {"evet", "yes"},
        }
        for year, spi, state, anom, rho, monotonic in pattern.findall(text)
    ]


def risk_raster_path(scenario: str) -> Path:
    return PROCESSED / f"risk_class_{scenario}.tif"


def raster_class_stats(scenario: str) -> dict[str, Any] | None:
    """Sınıf paylarını doğrudan raster'dan sayar.

    Neden rapordan değil: rapor ile raster birbirinden bağımsız üretiliyor ve
    ayrı zamanlarda tazeleniyor. Haritadaki kaplama raster'dan geldiği için
    yanındaki yüzdeler de aynı raster'dan gelmeli — yoksa aynı sayfada aynı
    şeyin iki farklı değeri görünür.
    """
    import rasterio

    path = risk_raster_path(scenario)
    if not path.exists():
        return None

    with rasterio.open(path) as src:
        band = src.read(1)
        nodata = src.nodata
        px_area_km2 = abs(src.transform.a * src.transform.e) / 1e6

    counts: dict[int, int] = {}
    for value in np.unique(band):
        if nodata is not None and value == nodata:
            continue
        v = int(round(float(value)))
        if v <= 0:
            continue
        counts[v] = int((band == value).sum())

    total = sum(counts.values())
    masked_px = int(band.size - total)
    return {
        "counts": counts,
        "total_pixels": total,
        "pixel_area_km2": px_area_km2,
        "masked": {
            "pixels": masked_px,
            "area_km2": round(masked_px * px_area_km2, 1),
        },
        "source_raster": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        "raster_mtime": date.fromtimestamp(path.stat().st_mtime).isoformat(),
    }


def build_map_overlay(
    scenario: str, palette: list[str], out_png: Path
) -> dict[str, Any] | None:
    """Risk sınıfı raster'ından web haritası için kaplama PNG'si üretir.

    Neden matplotlib figürü kullanılmıyor: `outputs/figures/risk_map_*.png`
    bir FİGÜRDÜR — başlık, eksen, lejant ve ölçek çubuğu içerir; veri
    pikselleri görüntünün yalnızca bir bölümünü kaplar. Onu coğrafi
    sınırlara germek raster'ı kaydırır ve ölçeğini bozar.

    Buradaki kaplama sınıf raster'ının kendisinden üretiliyor: EPSG:4326'ya
    yeniden projekte ediliyor (Leaflet'in beklediği CRS), config paletiyle
    renklendiriliyor, maskeli pikseller tamamen şeffaf bırakılıyor ve
    gerçek sınırları JSON'a yazılıyor. Kenarlık, yazı, dolgu yok.

    Raster yerelde yoksa (repoya girmiyor) None döner; arayüz o zaman
    statik figüre düşer.
    """
    import rasterio
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    src_path = PROCESSED / f"risk_class_{scenario}.tif"
    if not src_path.exists():
        return None

    from PIL import Image

    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, "EPSG:4326", src.width, src.height, *src.bounds
        )
        dst = np.zeros((height, width), dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs="EPSG:4326",
            # Sınıf değerleri KATEGORİKTİR: bilinear ara değer üretip
            # var olmayan sınıflar uydururdu.
            resampling=Resampling.nearest,
            src_nodata=src.nodata,
            dst_nodata=0,
        )

    classes = np.rint(dst).astype(np.int16)
    rgba = np.zeros((*classes.shape, 4), dtype=np.uint8)
    for i, hex_color in enumerate(palette, start=1):
        r, g, b = (int(hex_color.lstrip("#")[j : j + 2], 16) for j in (0, 2, 4))
        sel = classes == i
        rgba[sel] = (r, g, b, 255)
    # Sınıf dışı (maskeli / grid dışı) piksel tam şeffaf kalır.

    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(out_png, optimize=True)

    west, north = transform * (0, 0)
    east, south = transform * (width, height)
    return {
        "url": f"data/{out_png.name}",
        # Leaflet ImageOverlay: [[güney, batı], [kuzey, doğu]]
        "bounds": [[south, west], [north, east]],
        "width": width,
        "height": height,
        "source_raster": str(src_path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", default=None, help="senaryo adı (varsayılan: config)")
    args = ap.parse_args()

    cfg = load_config(scenario=args.scenario)
    scenario = cfg.scenario

    # --- AHP: ağırlıklar projenin kendi çözücüsünden gelir, rapordan değil --
    result = solve_from_config(cfg)
    sources = cfg["data_sources"]

    ahp_report = _read_report(f"ahp_{scenario}.md")
    effective = _parse_effective_contribution(ahp_report)

    criteria = []
    for name, weight in zip(result.criteria, result.weights):
        meta = cfg.criterion(name)
        eff = effective.get(name, {})
        src_key = meta.get("source")
        src = sources.get(src_key, {}) if src_key else {}
        criteria.append(
            {
                "key": name,
                "label": meta.get("label", name),
                "unit": meta.get("unit"),
                "weight": round(float(weight), 4),
                "effective_pct": eff.get("effective_pct"),
                "used_range": eff.get("used_range"),
                "higher_is_riskier": meta.get("higher_is_riskier"),
                "source": {
                    "key": src_key,
                    "provider": src.get("provider"),
                    "collection": src.get("collection"),
                }
                if src_key
                else None,
            }
        )

    palette = cfg["classification"]["colors"]
    palette_dark = cfg["classification"].get("colors_dark", palette)
    labels = cfg["classification"]["labels"]

    # Sınıf istatistiklerinin kaynağı: raster varsa raster, yoksa rapor.
    # Rapor ve raster ayrı zamanlarda tazeleniyor; harita kaplaması
    # raster'dan geldiği için yüzdeler de oradan gelmeli.
    stats = raster_class_stats(scenario)
    report_classes = {c["class"]: c for c in _parse_risk_classes(ahp_report)}
    report_mtime = date.fromtimestamp(
        (REPORTS / f"ahp_{scenario}.md").stat().st_mtime
    ).isoformat()

    if stats:
        classes_source = "raster"
        # Rapor raster'dan eskiyse Jenks sınırları o raster'a ait değildir;
        # güvenilmeyen sayıyı göstermek yerine boş bırakılır.
        report_is_stale = report_mtime < stats["raster_mtime"]
        classes = [
            {
                "class": k,
                "label": labels[k],
                "upper_bound": None
                if report_is_stale
                else report_classes.get(k, {}).get("upper_bound"),
                "pixels": stats["counts"][k],
                "share_pct": round(100 * stats["counts"][k] / stats["total_pixels"], 1),
                "area_km2": round(stats["counts"][k] * stats["pixel_area_km2"], 1),
            }
            for k in sorted(stats["counts"])
        ]
        masked = stats["masked"]
    else:
        classes_source = "report"
        report_is_stale = False
        classes = list(report_classes.values())
        masked = _parse_masked(ahp_report)

    for row in classes:
        i = row["class"] - 1
        row["color"] = palette[i]
        row["color_dark"] = palette_dark[i]

    bbox = cfg["aoi"]["bbox_wgs84"]

    summary: dict[str, Any] = {
        "generated": date.today().isoformat(),
        "scenario": scenario,
        "project": {
            "name": cfg["project"]["name"],
            "version": cfg["project"]["version"],
            "aoi_name": cfg["aoi"]["name"],
        },
        "grid": {
            "crs": cfg.crs,
            "resolution_m": cfg.resolution,
            # [min_lon, min_lat, max_lon, max_lat] -> Leaflet [[S,W],[N,E]]
            "bbox_wgs84": bbox,
            "leaflet_bounds": [[bbox[1], bbox[0]], [bbox[3], bbox[2]]],
        },
        "ahp": {
            "n_criteria": len(result.criteria),
            "lambda_max": round(result.lambda_max, 4),
            "consistency_index": round(result.consistency_index, 4),
            "consistency_ratio": round(result.consistency_ratio, 4),
            "cr_threshold": float(cfg["ahp"]["consistency"]["max_cr"]),
            "criteria": criteria,
        },
        "classification": {
            "method": cfg["classification"]["method"],
            "n_classes": cfg["classification"]["n_classes"],
            "classes": classes,
            "total_area_km2": round(sum(c["area_km2"] for c in classes), 1),
            "masked": masked,
            # Kaynak izlenebilirliği: hangi dosyadan geldiği ve raporun
            # raster'dan eski olup olmadığı arayüzde görünsün.
            "source": classes_source,
            "source_raster": stats["source_raster"] if stats else None,
            "report_is_stale": report_is_stale,
        },
    }

    try:
        operational = _read_report("operational_test.md")
    except ExportError:
        operational = ""
    summary["irrigation_effect"] = _parse_irrigation_effect(operational)
    summary["operational_years"] = _parse_yearly_operational(operational)

    summary["map_overlay"] = build_map_overlay(
        scenario, palette, WEB_DIR / f"risk_overlay_{scenario}.png"
    )

    WEB_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DATA.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Yazıldı: {WEB_DATA.relative_to(PROJECT_ROOT)}")
    print(f"  senaryo          : {scenario}")
    print(f"  kriter           : {len(criteria)}  (CR = {result.consistency_ratio:.4f})")
    print(f"  risk sınıfı      : {len(classes)}")
    print(f"  toplam alan      : {summary['classification']['total_area_km2']} km²")
    print(f"  sulama etkisi    : {len(summary['irrigation_effect'])} yıl")
    print(f"  operasyonel yıl  : {len(summary['operational_years'])}")
    ov = summary["map_overlay"]
    print(f"  harita kaplaması : {ov['width']}x{ov['height']} px" if ov else "  harita kaplaması : yok (raster yerelde bulunamadı)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
