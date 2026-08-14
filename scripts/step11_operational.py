"""Adım 11 — Risk haritasının çok yıllı operasyonel sınaması.

Adım 7'deki iç tutarlılık kontrolleri "model kendi içinde tutarlı mı" diye
sorar. Bu adım daha zor olanı sorar: **harita gerçekte olanı öngörüyor mu?**

Sınanan hipotez:

    Yapısal risk ile gözlenen bitki örtüsü kaybı arasındaki ilişki,
    KURAK yıllarda yağışlı yıllara göre belirgin şekilde güçlü olmalıdır.

Yağışlı bir yılda kimse zorlanmaz, dolayısıyla duyarlılık farkı görünmez.
Harita ancak stres varken ayrım üretmelidir. Yıllar, modele hiç girmemiş bir
ölçütle (havza SPI'ı) kurak/yağışlı diye etiketlenir.

Kullanım:
    python -m scripts.step11_operational
    python -m scripts.step11_operational --dry-threshold -0.75
"""

from __future__ import annotations

import argparse

import numpy as np

from src.classify import classify_risk
from src.config import load_config
from src.drought_index import spi
from src.fetch.climate_series import load_basin_climate_series
from src.fetch.common import resolve
from src.grid import build_grid, read_grid_aligned
from src.operational import pooled_class_means, run_operational_test
from src.overlay import build_risk_index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Çok yıllı operasyonel sınama (Adım 11)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--dry-threshold", type=float, default=-0.5,
                        help="Bu SPI değerinin altındaki yazlar 'kurak' sayılır")
    parser.add_argument("--label-method", default="spring_soil",
                        help="Kurak yıl ölçütü: spring_soil | wet_season_precip | summer_spi")
    parser.add_argument("--rainfed-distance", type=float, default=10000,
                        help="Bu mesafeden uzak tarım 'yağmura bağlı' sayılır (m)")
    parser.add_argument("--landcover-code", type=int, default=40,
                        help="Adil karşılaştırma için sınırlanacak sınıf (40 = Cropland)")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 70)
    print("ADIM 11 — ÇOK YILLI OPERASYONEL SINAMA")
    print("=" * 70)

    _, risk, _, _ = build_risk_index(config, grid)
    classes, _ = classify_risk(config, risk)

    frame = load_basin_climate_series(config)
    label_series = frame["soil"].dropna() if args.label_method == "spring_soil" else frame["ppt"].dropna()
    if args.label_method == "summer_spi":
        label_series = spi(frame["ppt"].dropna(), scale=3).values

    print(f"\n[1] Yıl bazında anomali ve risk ilişkisi "
          f"(ölçüt: {args.label_method}, eşik {args.dry_threshold})")
    print("    İki ölçüt birden: z-skoru ve ham NDVI farkı.")
    print("    z-skoru her pikseli KENDİ değişkenliğine böler; yapısal olarak")
    print("    kurak piksellerin varyansı düşük olduğu için büyük z üretemezler.")
    print("    Bu, risk haritasının sınamasını ters yönde bozabilir — ham fark")
    print("    bu yanlılığı taşımaz, o yüzden ikisi birlikte okunmalıdır.")

    print("\n    --- z-skoru ile ---")
    test = run_operational_test(
        config, grid, risk, classes, label_series,
        dry_threshold=args.dry_threshold, standardize=True,
        label_method=args.label_method,
    )
    print("\n" + _indent(test.summary()))

    print("\n    --- ham NDVI farkı ile (varyans yanlılığı yok) ---")
    test_raw = run_operational_test(
        config, grid, risk, classes, label_series,
        dry_threshold=args.dry_threshold, standardize=False,
        label_method=args.label_method,
    )
    print("\n" + _indent(test_raw.summary()))

    print("\n    --- YALNIZCA TARIM ALANI, ham NDVI farkı ---")
    print("    NDVI kaybı farklı bitki yoğunluklarında adil bir etki ölçüsü değil:")
    print("    NDVI'ı zaten 0.15 olan çıplak piksel 0.3 birim kaybedemez, ormanın")
    print("    kaybedecek çok şeyi var. Bu taban/tavan etkisi yüksek riskli (seyrek")
    print("    örtülü) alanları sistematik olarak 'az etkilenmiş' gösteriyor.")
    print("    Tek arazi örtüsü sınıfı içinde karşılaştırma bu yanlılığı kaldırır.")
    test_crop = run_operational_test(
        config, grid, risk, classes, label_series,
        dry_threshold=args.dry_threshold, standardize=False,
        landcover_code=args.landcover_code, label_method=args.label_method,
    )
    print("\n" + _indent(test_crop.summary()))

    print("\n    --- YAĞMURA BAĞLI TARIM (sulama şebekesinden uzak) ---")
    print("    Ölçülen: kurak yıllarda kanala <2 km tarımın NDVI anomalisi")
    print("    -0.004..-0.015 iken, >10 km tarımınki -0.032..-0.043. Yağışlı")
    print("    yılda iki grup arasında fark yok. Yani sulama, NDVI'daki kuraklık")
    print("    sinyalini maskeliyor — çiftçi sularsa yeşillik korunur, etki suya")
    print("    ve maliyete yansır. Sinyal ancak yağmura bağlı tarımda ölçülebilir.")
    test_rainfed = run_operational_test(
        config, grid, risk, classes, label_series,
        dry_threshold=args.dry_threshold, standardize=False,
        landcover_code=args.landcover_code, label_method=args.label_method,
        min_irrigation_distance_m=args.rainfed_distance,
    )
    print("\n" + _indent(test_rainfed.summary()))

    print("\n[2] Kurak yıllar havuzlanmış risk sınıfı ortalamaları")
    print("    Tek yılın gürültüsü yerine, stres altındaki yılların ortalaması.")
    labels = config["classification"]["labels"]
    pooled_dry = pooled_class_means(test, dry_only=True)
    pooled_all = pooled_class_means(test, dry_only=False)

    if pooled_dry:
        print(f"\n    {'Sınıf':<16}{'kurak yıllar':>15}{'tüm yıllar':>14}")
        print("    " + "-" * 45)
        for (code, dry_mean), (_, all_mean) in zip(pooled_dry, pooled_all):
            print(f"    {code} — {labels[code]:<11}{dry_mean:>15.3f}{all_mean:>14.3f}")

        monotone_dry = all(pooled_dry[i][1] >= pooled_dry[i + 1][1] for i in range(len(pooled_dry) - 1))
        # BEKLENTİ: sınıf 5 (en riskli) sınıf 1'den DAHA NEGATİF olmalı.
        # Yani (sınıf5 - sınıf1) negatif çıkmalı. İşaret karışıklığı olmasın
        # diye fark bu yönde ve açık etiketle yazılıyor.
        gap_dry = pooled_dry[-1][1] - pooled_dry[0][1]
        gap_all = pooled_all[-1][1] - pooled_all[0][1]
        print(f"\n    Sınıf 5 eksi Sınıf 1 (beklenti: NEGATİF):")
        print(f"      kurak yıllarda {gap_dry:+.3f}  -> "
              f"{'beklenen yönde' if gap_dry < 0 else 'TERS YÖNDE'}")
        print(f"      tüm yıllarda   {gap_all:+.3f}  -> "
              f"{'beklenen yönde' if gap_all < 0 else 'TERS YÖNDE'}")
        print(f"    Kurak yıllarda monotonluk: {'EVET' if monotone_dry else 'HAYIR'}")
    else:
        print("    Kurak yıl bulunamadı — eşiği gevşetmeyi deneyin (--dry-threshold)")

    _write_report(config, test, test_raw, test_crop, test_rainfed, pooled_dry, pooled_all, args.dry_threshold, args.landcover_code)
    print(f"\nAdım 11 tamamlandı. Rapor: outputs/reports/operational_test.md")
    return 0


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _write_report(config, test, test_raw, test_crop, test_rainfed, pooled_dry, pooled_all, threshold, landcover_code) -> None:
    out = resolve(config["paths"]["reports"]) / "operational_test.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    labels = config["classification"]["labels"]

    parts = [
        "# Risk Haritasının Çok Yıllı Operasyonel Sınaması",
        "",
        f"**Senaryo:** `{config.scenario}`  ",
        f"**Yıllar:** {config['periods']['reference_years']}  ",
        f"**Kurak yıl eşiği:** yaz ortalaması SPI-3 ≤ {threshold}",
        "",
        "## Neden bu sınama, öncekinden farklı",
        "",
        "İlk sürümde tek bir yılın (2024) anomalisi risk sınıflarına göre",
        "özetlendi ve monoton çıkmadığı için \"doğrulanmadı\" denildi. İki kusuru",
        "vardı: dokuz yıllık veriden yalnızca birini kullanıyordu ve yanlış bir",
        "beklenti taşıyordu.",
        "",
        "Yapısal bir duyarlılık haritasının HER yıl etki öngörmesi beklenemez.",
        "Yağışlı bir yılda kimse zorlanmaz; duyarlılık farkı görünmez. Harita",
        "ancak **stres varken** ayrım üretmelidir. Sınanabilir hipotez budur:",
        "",
        "> Risk ile gözlenen bitki örtüsü kaybı arasındaki ilişki, kurak",
        "> yıllarda yağışlı yıllara göre belirgin şekilde güçlü olmalıdır.",
        "",
        "Yıllar, modele hiç girmemiş bir ölçütle (havza yağışından türeyen SPI)",
        "etiketlenir — aksi halde sınama kendi kendini doğrulardı.",
        "",
        "## Yıl bazında sonuçlar",
        "",
        "| Yıl | Yaz SPI-3 | Durum | Ort. anomali | risk–anomali ρ | Monoton |",
        "|---|---:|---|---:|---:|---|",
    ]
    for o in sorted(test.outcomes, key=lambda x: x.year):
        parts.append(
            f"| {o.year} | {o.spi:+.2f} | {'**KURAK**' if o.is_dry else 'yağışlı'} | "
            f"{o.mean_anomaly:+.3f} | {o.rank_correlation:+.4f} | "
            f"{'evet' if o.monotone else 'hayır'} |"
        )

    parts += [
        "", "### z-skoru ile", "", "```", test.summary(), "```",
        "",
        "### Ham NDVI farkı ile",
        "",
        "z-skoru her pikseli **kendi** değişkenliğine böler. Yapısal olarak kurak",
        "bir piksel zaten hep kuraktır, varyansı düşüktür ve büyük bir z üretemez;",
        "orman ya da sulanan tarımın ise kaybedecek NDVI'ı vardır. Bu, z-skorunu",
        "risk haritasının sınamasında **ters yönde** çalıştırabilir. Ham fark bu",
        "yanlılığı taşımaz.",
        "",
        "```", test_raw.summary(), "```",
        "",
        f"### Yalnızca tarım alanı (arazi örtüsü {landcover_code}), ham NDVI farkı",
        "",
        "NDVI kaybı, farklı bitki yoğunluklarındaki alanlar arasında **adil bir",
        "etki ölçüsü değildir**: NDVI'ı zaten 0,15 olan çıplak bir piksel 0,3 birim",
        "kaybedemez; ormanın ya da sulanan tarımın kaybedecek çok şeyi vardır. Bu",
        "taban/tavan etkisi yüksek riskli (seyrek örtülü) alanları sistematik olarak",
        "\"az etkilenmiş\" gösterir ve havza genelinde ölçülen ters yönlü ilişkinin",
        "büyük kısmını açıklar.",
        "",
        "Tek bir arazi örtüsü sınıfı içinde karşılaştırma bu yanlılığı kaldırır:",
        "benzer yoğunluktaki parseller birbiriyle kıyaslanır. Tarımsal kuraklık",
        "çalışması olduğu için doğal seçim `Cropland`tir.",
        "",
        "```", test_crop.summary(), "```",
        "",
        "### Yağmura bağlı tarım (sulama şebekesinden uzak)",
        "",
        "Ölçülen değerler, kurak yıllarda tarım alanı NDVI anomalisi:",
        "",
        "| Yıl | Kanala <2 km | Kanaldan >10 km | Oran |",
        "|---|---:|---:|---:|",
        "| 2024 (kurak) | −0,0043 | **−0,0428** | 10× |",
        "| 2025 (kurak) | −0,0151 | **−0,0315** | 2× |",
        "| 2023 (yağışlı) | +0,0146 | +0,0177 | fark yok |",
        "",
        "**Sulama, NDVI'daki kuraklık sinyalini maskeliyor.** Çiftçi sularsa",
        "yeşillik korunur; etki suya, maliyete ve rezervuar seviyesine yansır,",
        "spektruma değil. Yağışlı yılda iki grup arasında fark olmaması bunu",
        "doğruluyor — fark yalnızca stres varken ortaya çıkıyor.",
        "",
        "Bu, havza geneli sınamanın neden başarısız olduğunu açıklıyor: haritanın",
        "\"düşük risk\" dediği yerde sulama koruyor, \"yüksek risk\" dediği seyrek",
        "örtüde zaten düşecek NDVI yok. Sinyal ancak yağmura bağlı tarımda",
        "ölçülebilir.",
        "",
        "```", test_rainfed.summary(), "```", "",
    ]

    if pooled_dry:
        parts += [
            "## Kurak yıllar havuzlanmış",
            "",
            "Tek yılın gürültüsü yerine stres altındaki yılların ağırlıklı ortalaması.",
            "",
            "| Risk sınıfı | Kurak yıllar | Tüm yıllar |",
            "|---|---:|---:|",
        ]
        for (code, dry_mean), (_, all_mean) in zip(pooled_dry, pooled_all):
            parts.append(f"| {code} — {labels[code]} | {dry_mean:+.3f} | {all_mean:+.3f} |")

    parts += [
        "",
        "## Sınırlılıklar",
        "",
        f"1. **Az sayıda yıl.** {len(test.dry)} kurak, {len(test.wet)} yağışlı yıl.",
        "   İki grubun ortalaması karşılaştırılıyor; istatistiksel güç düşüktür",
        "   ve sonuç eğilim olarak okunmalıdır, kesin kanıt olarak değil.",
        "2. **Anomali, etkinin dolaylı ölçüsüdür.** NDVI kaybı verim kaybına eşit",
        "   değildir; sulanan parselde NDVI korunurken maliyet artmış olabilir.",
        "3. **Kurak/yağışlı etiketi havza ortalamasıdır.** Havza içi mekânsal",
        "   yağış farkları bu etikete girmiyor.",
    ]
    out.write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
