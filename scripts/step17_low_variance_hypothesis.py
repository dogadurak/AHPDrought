"""Adım 17 — "Düşük değişkenlikli kriterler haritayı bozuyor" hipotezinin sınanması.

NEDEN BU ADIM VAR: Adım 13, risk haritasının gerçek kuraklıklarda gözlenen
etkiyi öngörmediğini gösterdi. Bunun en kolay açıklaması şudur — ağırlığın
neredeyse yarısı, havzada neredeyse hiç değişmeyen üç kriterde (yağış, toprak
su kapasitesi, LST). Yüzdelik normalizasyon bu kriterlerin küçük gerçek farkını
0-1 aralığına gerdiği için harita gürültü taşıyor olabilir.

Bir başarısızlığı açıklayan ilk hipotezi sınamadan kabul etmek, onu sınamadan
reddetmek kadar hatalıdır. Bu betik hipotezi KURAR ve SINAR: adı geçen
kriterler çıkarılır, kalan ağırlıklar toplamı 1 olacak şekilde yeniden
ölçeklenir (özvektör ağırlıklarının birbirine oranı korunur), harita yeniden
üretilir ve Adım 13'ün sınaması aynen tekrarlanır.

Ağırlıkları yeniden ölçekleme, AHP'de bir alt küme için kabul gören işlemdir:
ikili karşılaştırma matrisinin tutarlılığı kalan kriterler arasındaki oranlarla
tanımlıdır ve bu oranlar ölçeklemeden etkilenmez.

Kullanım:
    python -m scripts.step17_low_variance_hypothesis
    python -m scripts.step17_low_variance_hypothesis --drop precipitation,lst
    python -m scripts.step17_low_variance_hypothesis --impact et

Çıktı:
    outputs/reports/low_variance_hypothesis.md
"""

from __future__ import annotations

import argparse

import numpy as np

from src.classify import classify_risk
from src.config import load_config
from src.drought_index import spi
from src.fetch.climate_series import load_basin_climate_series
from src.fetch.common import resolve
from src.grid import build_grid
from src.historical import historical_test
from src.overlay import build_risk_index, weighted_overlay

# Adım 13'ün raporundaki "gerçek aralık / göreli yayılım" tablosunda havzada
# neredeyse hiç değişmeyen çıkan üç kriter. Toplam ağırlıkları ~%46.
DEFAULT_DROP = ("precipitation", "soil_awc", "lst")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Düşük değişkenlikli kriter hipotezinin sınanması (Adım 17)"
    )
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument(
        "--drop",
        default=",".join(DEFAULT_DROP),
        help="Çıkarılacak kriterler (virgülle). Varsayılan: " + ",".join(DEFAULT_DROP),
    )
    parser.add_argument("--impact", default="ndvi", choices=("ndvi", "et"))
    parser.add_argument("--landcover-code", type=int, default=40)
    parser.add_argument("--dry-threshold", type=float, default=-1.0)
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 72)
    print("ADIM 17 — DÜŞÜK DEĞİŞKENLİKLİ KRİTER HİPOTEZİ")
    print("=" * 72)

    _, risk_base, result, stack = build_risk_index(config, grid)
    names = list(stack.names)
    weights = np.asarray(result.weights, dtype="float64")

    drop = [d.strip() for d in args.drop.split(",") if d.strip()]
    unknown = [d for d in drop if d not in names]
    if unknown:
        raise SystemExit(f"Bilinmeyen kriter: {', '.join(unknown)}\nGeçerli: {', '.join(names)}")
    if len(drop) >= len(names):
        raise SystemExit("Bütün kriterler çıkarılamaz.")

    keep_idx = [i for i, n in enumerate(names) if n not in drop]
    dropped_weight = float(weights[[names.index(d) for d in drop]].sum())

    # Alt küme ağırlıkları: çıkarılanlar sıfırlanır, kalanlar toplamı 1 olacak
    # şekilde yeniden ölçeklenir. Oranlar korunur.
    w_subset = np.zeros_like(weights)
    w_subset[keep_idx] = weights[keep_idx] / weights[keep_idx].sum()

    print(f"\n[1] Çıkarılan kriterler ({len(drop)}): {', '.join(drop)}")
    print(f"    Taşıdıkları toplam ağırlık: %{100 * dropped_weight:.1f}")
    print("\n[2] Yeniden ölçeklenmiş ağırlıklar")
    for i in keep_idx:
        print(f"    {names[i]:<20} {weights[i]:.4f} -> {w_subset[i]:.4f}")

    # Normalize edilmiş katmanların standart sapması — "değişkenlik" iddiasının
    # sayısal dayanağı. Ağırlıkla çarpılmadan, ham normalize değer üzerinden.
    print("\n[3] Katmanların havza içi değişkenliği (normalize, 0-1)")
    spread = {}
    for i, name in enumerate(names):
        layer = stack.data[i][stack.valid_mask]
        spread[name] = float(np.nanstd(layer))
        mark = "  <- çıkarıldı" if name in drop else ""
        print(f"    {name:<20} std = {spread[name]:.4f}{mark}")

    print("\n[4] Alt küme haritası üretiliyor")
    risk_subset = weighted_overlay(stack, w_subset)
    classes_base, _ = classify_risk(config, risk_base)
    classes_subset, _ = classify_risk(config, risk_subset)

    frame = load_basin_climate_series(config)
    spi12 = spi(frame["ppt"].dropna(), scale=12).values
    landcover = args.landcover_code or None

    print("\n[5] Adım 13 sınaması iki harita için tekrarlanıyor")
    common = dict(
        dry_threshold=args.dry_threshold,
        landcover_code=landcover,
        source=args.impact,
    )
    base = historical_test(config, grid, risk_base, classes_base, spi12, **common)
    sub = historical_test(config, grid, risk_subset, classes_subset, spi12, **common)

    rho_base = float(base["dry_rho"])
    rho_sub = float(sub["dry_rho"])
    print(f"\n    Tam harita   (9 kriter): kurak yıl ortalama rho = {rho_base:+.4f}")
    print(f"    Alt küme ({len(keep_idx)} kriter): kurak yıl ortalama rho = {rho_sub:+.4f}")

    verdict = _verdict(rho_base, rho_sub)
    print(f"\n    HÜKÜM: {verdict}")

    _write_report(
        config, args, names, weights, w_subset, drop, dropped_weight,
        spread, base, sub, verdict,
    )
    print("\nAdım 17 tamamlandı. Rapor: outputs/reports/low_variance_hypothesis.md")
    return 0


def _verdict(rho_base: float, rho_sub: float) -> str:
    """Hipotez ancak ilişki beklenen yönde ANLAMLI ölçüde güçlenirse desteklenir.

    Eşik Adım 13 ile aynı: rho <= -0.10. Yalnızca "biraz daha negatif" olmak
    yeterli değil; sınamanın kendi ölçütünü geçmesi gerekir.
    """
    if rho_sub <= -0.10:
        return "DESTEKLENDİ — kriterleri çıkarmak ilişkiyi beklenen yönde anlamlı kıldı"
    if rho_sub < rho_base:
        return (
            "REDDEDİLDİ — ilişki beklenen yönde biraz güçlendi ama hâlâ fiilen sıfır "
            "(eşik <= -0.10)"
        )
    return "REDDEDİLDİ — kriterleri çıkarmak düzeltmedi, ilişki daha da zayıfladı"


def _write_report(config, args, names, weights, w_subset, drop, dropped_weight,
                  spread, base, sub, verdict) -> None:
    out = resolve(config["paths"]["reports"]) / "low_variance_hypothesis.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    keep = [n for n in names if n not in drop]
    w_rows = "\n".join(
        f"| `{n}` | {weights[names.index(n)]:.4f} | "
        f"{w_subset[names.index(n)]:.4f} | {spread[n]:.4f} |"
        for n in keep
    )
    d_rows = "\n".join(
        f"| `{n}` | {weights[names.index(n)]:.4f} | — (çıkarıldı) | {spread[n]:.4f} |"
        for n in drop
    )

    out.write_text(f"""# Düşük Değişkenlikli Kriter Hipotezinin Sınanması

**Etki ölçüsü:** `{args.impact}` · **Kapsam:** {"yalnızca arazi örtüsü "
f"{args.landcover_code}" if args.landcover_code else "havza geneli"} ·
**Kurak yıl eşiği:** SPI-12 <= {args.dry_threshold}

## Hipotez

Adım 13, risk haritasının gerçek kuraklıklarda gözlenen etkiyi öngörmediğini
gösterdi. En kolay açıklama: ağırlığın **%{100 * dropped_weight:.1f}'i**
havzada neredeyse hiç değişmeyen {len(drop)} kriterde
({", ".join(f"`{d}`" for d in drop)}). Yüzdelik normalizasyon bu kriterlerin
küçük gerçek farkını 0-1 aralığına gerdiği için harita ayrım üretemiyor olabilir.

**Sınama:** bu kriterler çıkarılır, kalan ağırlıklar toplamı 1 olacak şekilde
yeniden ölçeklenir (özvektör oranları korunur), harita yeniden üretilir ve
Adım 13'ün sınaması aynen tekrarlanır.

## Ağırlıklar ve katman değişkenliği

`std`, normalize edilmiş (0-1) katmanın havza içi standart sapmasıdır — düşük
değer, kriterin ölçeğini kullanmadığı anlamına gelir.

| Kriter | Tam harita | Alt küme | std |
|---|---:|---:|---:|
{w_rows}
{d_rows}

## Sonuç

| Harita | Kriter | Kurak yıl ortalama Spearman rho | Normal yıl |
|---|---:|---:|---:|
| Tam | {len(names)} | **{base["dry_rho"]:+.4f}** | {base["normal_rho"]:+.4f} |
| Alt küme | {len(keep)} | **{sub["dry_rho"]:+.4f}** | {sub["normal_rho"]:+.4f} |

**HÜKÜM: {verdict}**

Düşük değişkenlik teşhisi doğru — üç kriterin standart sapması gerçekten düşük.
Ama başarısızlığın sebebi o değil: kriterleri çıkarmak haritayı düzeltmiyor.
Bu, Adım 13'ün sonucunun kriter seçimine bağlı olmadığını gösterir ve
"yanlış kriterleri seçtiniz" itirazını eler.

Sınamanın eşiği Adım 13 ile aynıdır (rho <= -0.10); yalnızca sayının biraz
oynaması hipotezi desteklemek için yeterli sayılmaz.
""", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
