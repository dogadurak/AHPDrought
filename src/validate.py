"""Adım 7 — Risk haritasının doğrulanması.

DÜRÜSTLÜK NOTU (raporda da yer alır): tam bağımsız bir doğrulama, saha verisi
gerektirir — TÜİK ilçe bazında verim istatistikleri, DSİ sulama kayıtları veya
MGM kuraklık indeksi yayınları. Bunların hiçbirinin açık API'si yok; manuel
indirme "her adım tek başına çalıştırılabilir" kısıtını kırardı. Bu yüzden bu
modül üç seviyeli, sınırlarını açıkça bildiren bir doğrulama yapar:

1. İÇSEL TUTARLILIK (tam bağımsız değil, ama gerekli koşul)
   - Senaryo dayanıklılığı: eğimin risk yönü ters çevrildiğinde harita ne kadar
     değişiyor? Sonuç bu tek tartışmalı karara aşırı bağımlıysa savunulamaz.
   - Ağırlık duyarlılığı: Adım 4'teki ±%10 analizi.

2. YARI BAĞIMSIZ SİNYAL
   - Mevsimsel NDVI genliği (ilkbahar tepe - yaz dip). Bu, kriter olarak
     kullanılan "kurak dönem NDVI SEVİYESİ"nden farklı bir büyüklüktür: seviye
     ne kadar yeşil olduğunu, genlik ise yaz boyunca ne kadar kaybettiğini
     ölçer. Yine de aynı sensörden türediği için kısmi döngüsellik vardır ve
     bu, sonucun kanıt değerini sınırlar.

3. KATMANLI ÖZET
   - Arazi örtüsü ve yükseklik kuşaklarına göre risk dağılımı. Beklenen yönde
     çıkmazsa (ör. ormanın tarımdan riskli görünmesi) model hatalıdır.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .classify import classify_risk
from .config import Config
from .fetch.common import interim_path, resolve
from .grid import TargetGrid, read_grid_aligned


def _masked(path: Path, grid: TargetGrid, config: Config) -> np.ndarray:
    array = read_grid_aligned(path, grid).astype("float32")
    return np.where(array == np.float32(config.nodata), np.nan, array)


# --- 1. Senaryo dayanıklılığı -----------------------------------------------


def scenario_agreement(config: Config, grid: TargetGrid) -> dict:
    """İki eğim senaryosunun risk sınıfı haritalarını karşılaştırır."""
    from .config import load_config
    from .criteria.build import build_criterion
    from .overlay import build_risk_index

    results = {}
    for scenario in config["scenarios"]["definitions"]:
        cfg = load_config(config.path, scenario=scenario)

        # Senaryoya bağlı kriterler o senaryo için henüz üretilmemiş olabilir.
        for name in cfg.criteria_order:
            if cfg.is_scenario_dependent(name) and not cfg.criterion_path(name).exists():
                build_criterion(name, cfg, grid)

        _, risk, _, _ = build_risk_index(cfg, grid)
        classes, _ = classify_risk(cfg, risk)
        results[scenario] = (risk, classes)

    names = list(results)
    (risk_a, cls_a), (risk_b, cls_b) = results[names[0]], results[names[1]]
    valid = np.isfinite(risk_a) & np.isfinite(risk_b)

    diff = np.abs(risk_a[valid] - risk_b[valid])
    same = cls_a[valid] == cls_b[valid]
    within_one = np.abs(cls_a[valid].astype(int) - cls_b[valid].astype(int)) <= 1

    return {
        "scenarios": names,
        "mean_abs_diff": float(diff.mean()),
        "max_abs_diff": float(diff.max()),
        "class_agreement": float(same.mean()),
        "within_one_class": float(within_one.mean()),
    }


# --- 2. Mevsimsel NDVI genliği ----------------------------------------------


def seasonal_amplitude(config: Config, grid: TargetGrid) -> np.ndarray | None:
    """İlkbahar tepe NDVI'ı ile yaz dip NDVI'ı arasındaki fark.

    Yüksek genlik = bitki örtüsü yaz boyunca çok şey kaybediyor = su stresi
    göstergesi.
    """
    year = config["periods"]["timeseries"]["year"]
    spring = config["periods"]["wet_season"]
    dry = config["periods"]["dry_season"]

    def stack(start: int, end: int) -> np.ndarray | None:
        layers = []
        for month in range(start, end + 1):
            path = interim_path(config, "ndvi_monthly", f"ndvi_{year}_{month:02d}.tif")
            if path.exists():
                layers.append(_masked(path, grid, config))
        return np.stack(layers) if layers else None

    spring_stack = stack(spring["start_month"], spring["end_month"])
    dry_stack = stack(dry["start_month"], dry["end_month"])
    if spring_stack is None or dry_stack is None:
        return None

    return (np.nanmax(spring_stack, axis=0) - np.nanmin(dry_stack, axis=0)).astype("float32")


def amplitude_by_class(classes: np.ndarray, amplitude: np.ndarray, n_classes: int) -> list[tuple[int, float, int]]:
    """Her risk sınıfı için ortalama mevsimsel NDVI genliği."""
    rows = []
    for code in range(1, n_classes + 1):
        selection = (classes == code) & np.isfinite(amplitude)
        if selection.sum() == 0:
            continue
        rows.append((code, float(np.nanmean(amplitude[selection])), int(selection.sum())))
    return rows


# --- 3. Katmanlı özet --------------------------------------------------------


def risk_by_landcover(config: Config, grid: TargetGrid, risk: np.ndarray) -> list[tuple[str, float, float]]:
    """Arazi örtüsü sınıfına göre ortalama risk indeksi."""
    from .config import load_json

    codes = read_grid_aligned(interim_path(config, "landcover.tif"), grid)
    lookup = load_json(config["data_sources"]["landcover"]["lookup_file"])["classes"]

    rows = []
    for code_str, entry in lookup.items():
        if entry.get("score") is None:
            continue
        selection = (codes == int(code_str)) & np.isfinite(risk)
        if selection.sum() < 1000:
            continue
        rows.append((entry["name"], float(risk[selection].mean()), 100 * float(selection.mean())))
    return sorted(rows, key=lambda r: r[1], reverse=True)


def risk_by_elevation(config: Config, grid: TargetGrid, risk: np.ndarray, bands: int = 5) -> list[tuple[str, float, int]]:
    """Yükseklik kuşaklarına göre ortalama risk indeksi."""
    dem = _masked(interim_path(config, "dem.tif"), grid, config)
    valid = np.isfinite(dem) & np.isfinite(risk)
    edges = np.percentile(dem[valid], np.linspace(0, 100, bands + 1))

    rows = []
    for i in range(bands):
        lo, hi = edges[i], edges[i + 1]
        selection = valid & (dem >= lo) & (dem < hi if i < bands - 1 else dem <= hi)
        if selection.sum() == 0:
            continue
        rows.append((f"{lo:,.0f}–{hi:,.0f} m", float(risk[selection].mean()), int(selection.sum())))
    return rows


# --- Rapor -------------------------------------------------------------------


def write_validation_report(
    config: Config, grid: TargetGrid, risk: np.ndarray, classes: np.ndarray
) -> Path:
    """Üç seviyeli doğrulama raporunu markdown olarak yazar."""
    n_classes = config["classification"]["n_classes"]
    labels = config["classification"]["labels"]

    parts = [
        "# Doğrulama Raporu",
        "",
        f"**Bölge:** {config['aoi']['name']}  ",
        f"**Senaryo:** `{config.scenario}`  ",
        f"**Grid:** {config.crs}, {config.resolution:g} m",
        "",
        "## Kapsam ve sınırlılıklar",
        "",
        "Tam bağımsız doğrulama saha verisi gerektirir (TÜİK ilçe bazında verim,",
        "DSİ sulama kayıtları, MGM kuraklık indeksi). Bu kaynakların açık API'si",
        "olmadığından ve manuel indirme projenin \"her adım tek başına",
        "çalıştırılabilir\" kısıtını kıracağından, bu rapor üç seviyeli ve sınırları",
        "açıkça bildirilen bir doğrulama sunar. Aşağıdaki sonuçlar modelin **iç",
        "tutarlılığını** ve **beklenen fiziksel yönlerle uyumunu** gösterir;",
        "gerçek kuraklık zararıyla doğrulanmış değildir.",
        "",
        "## 1. Senaryo dayanıklılığı",
        "",
        "Eğimin risk yönü literatürde tartışmalı olduğundan iki senaryo da üretildi.",
        "Sonuç bu tek karara aşırı duyarlıysa harita savunulamaz.",
        "",
    ]

    agreement = scenario_agreement(config, grid)
    parts += [
        f"| Karşılaştırma | `{agreement['scenarios'][0]}` vs `{agreement['scenarios'][1]}` |",
        "|---|---|",
        f"| Risk indeksi ortalama farkı | {agreement['mean_abs_diff']:.4f} |",
        f"| Risk indeksi maksimum farkı | {agreement['max_abs_diff']:.4f} |",
        f"| Aynı sınıfta kalan piksel | %{100 * agreement['class_agreement']:.1f} |",
        f"| En fazla 1 sınıf kayan piksel | %{100 * agreement['within_one_class']:.1f} |",
        "",
    ]

    parts += ["## 2. Mevsimsel NDVI genliği (yarı bağımsız)", ""]
    amplitude = seasonal_amplitude(config, grid)
    if amplitude is None:
        parts += ["Aylık NDVI kompozitleri eksik — bu kontrol atlandı.", ""]
    else:
        parts += [
            "Genlik = ilkbahar tepe NDVI − yaz dip NDVI. Kriter olarak kullanılan",
            "*kurak dönem NDVI seviyesi*nden farklı bir büyüklüktür, ama aynı",
            "sensörden türediği için kısmi döngüsellik taşır.",
            "",
            "**Beklenti:** risk sınıfı arttıkça mevsimsel genlik de artmalı.",
            "",
            "| Risk sınıfı | Ortalama mevsimsel NDVI düşüşü | Piksel |",
            "|---|---|---|",
        ]
        rows = amplitude_by_class(classes, amplitude, n_classes)
        for code, mean_amp, count in rows:
            parts.append(f"| {code} — {labels[code]} | {mean_amp:.4f} | {count:,} |")

        if len(rows) >= 2:
            monotone = all(rows[i][1] <= rows[i + 1][1] for i in range(len(rows) - 1))
            verdict = "beklenen yönde, monoton artıyor" if monotone else "monoton DEĞİL — incelenmeli"
            parts += ["", f"**Sonuç:** {verdict}."]
        parts.append("")

    parts += ["## 3. Katmanlı özet", "", "### Arazi örtüsüne göre ortalama risk", ""]
    parts += ["| Arazi örtüsü | Ortalama risk | Alan payı |", "|---|---|---|"]
    for name, mean_risk, share in risk_by_landcover(config, grid, risk):
        parts.append(f"| {name} | {mean_risk:.4f} | %{share:.1f} |")

    parts += ["", "### Yükseklik kuşağına göre ortalama risk", ""]
    parts += ["| Yükseklik | Ortalama risk | Piksel |", "|---|---|---|"]
    for band, mean_risk, count in risk_by_elevation(config, grid, risk):
        parts.append(f"| {band} | {mean_risk:.4f} | {count:,} |")

    parts += [
        "",
        "## Gerçek doğrulama için gereken",
        "",
        "- TÜİK bitkisel üretim istatistikleri: ilçe bazında bağ/zeytin/pamuk verimi,",
        "  kurak yıllar (2021) ile yaş yıllar (2024) karşılaştırması.",
        "- DSİ Demirköprü sulama şebekesi kayıtları: fiilen sulanan alanların sınırı.",
        "- MGM SPI/SPEI istasyon verisi: meteorolojik kuraklığın bağımsız ölçümü.",
        "- Saha örneklemi: yüksek risk sınıfında rastgele parsellerin yerinde kontrolü.",
        "",
        "Bunlar eklendiğinde bu rapor, mevcut iç tutarlılık kontrollerinin yerine",
        "değil, üzerine gelmelidir.",
    ]

    out = resolve(config["paths"]["reports"]) / "validation_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(parts), encoding="utf-8")
    return out
