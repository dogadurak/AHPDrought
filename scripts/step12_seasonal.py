"""Adım 12 — Mevsimsel öngörü: kış sonu durumundan yaz stresi.

Adım 10'da "SPI-3'ten 3 ay sonraki SPI-3" soruldu ve hiçbir beceri çıkmadı.
Sebep sorunun kendisiydi: iki SPI-3 penceresi hiç kesişmediği için paylaşılacak
bilgi yoktu.

Bu adım fiziksel olarak anlamlı soruyu sorar:

    Akdeniz ikliminde yaz yağışsızdır (Gediz'de temmuz-ağustos 3-5 mm).
    Yaz bitki örtüsünü belirleyen şey o yaz yağan yağmur değil, KIŞIN
    biriken sudur. Öyleyse: nisan sonunda bilinen durumdan, o yazın su
    stresini öngörebilir miyiz?

Değerlendirme kuralları aynı katılıkta: kronolojik bölme, iklimatoloji VE
kalıcılık taban çizgileri, katsayılar yalnızca eğitim döneminden. Fiziksel
gerekçe, beceri kanıtının yerine geçmez.

Kullanım:
    python -m scripts.step12_seasonal
    python -m scripts.step12_seasonal --target pdsi
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.config import load_config
from src.fetch.climate_series import load_basin_climate_series
from src.fetch.common import resolve
from src.seasonal import build_dataset, evaluate_seasonal, seasonal_skill_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mevsimsel öngörü (Adım 12)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--target", default="soil",
                        help="Yaz stresinin ölçüsü: soil | pdsi | ppt")
    parser.add_argument("--train-fraction", type=float, default=0.7)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    frame = load_basin_climate_series(config)

    print("=" * 76)
    print("ADIM 12 — MEVSİMSEL ÖNGÖRÜ: KIŞ SONU DURUMUNDAN YAZ STRESİ")
    print("=" * 76)

    available = list(frame.columns)
    print(f"\n[0] Seride bulunan değişkenler: {available}")
    if args.target not in available:
        raise SystemExit(
            f"Hedef '{args.target}' seride yok. Önce indirin:\n"
            "  python -m scripts.step10_forecast --fetch"
        )

    _climatology_check(frame)

    dry = config["periods"]["dry_season"]
    target_months = tuple(range(dry["start_month"], dry["end_month"] + 1))

    dataset = build_dataset(frame, target_months=target_months, target_column=args.target)
    print("\n[1] Öngörücülerin hedefle ilişkisi (tüm yıllar)")
    print("\n" + _indent(dataset.describe()))

    print("\n[2] Tahmin becerisi — kronolojik bölme, iki taban çizgisi")
    rows, learned = evaluate_seasonal(dataset, train_fraction=args.train_fraction)
    print("\n" + _indent(seasonal_skill_table(rows, learned, dataset)))

    best = _best(rows)
    print("\n[3] Sonuç")
    if best is None:
        print("    Hiçbir öngörücü her iki taban çizgisini birden geçemedi.")
        print("    Bu, kış sonu durumundan yaz stresinin öngörülemediği anlamına gelir.")
    else:
        print(f"    En iyi öngörücü: {best.name}")
        print(f"      iklimatolojiye karşı beceri : {best.skill_vs_climatology:+.3f}")
        print(f"      kalıcılığa karşı beceri     : {best.skill_vs_persistence:+.3f}")
        print(f"      test korelasyonu            : {best.correlation:+.3f}")
        print("    Bir öngörücünün işe yaraması için HER İKİ skorun da pozitif olması gerekir.")

    _write_report(config, dataset, rows, learned, best, args.target)
    _figure(config, dataset, learned)
    print("\nAdım 12 tamamlandı. Rapor: outputs/reports/seasonal_forecast.md")
    return 0


def _climatology_check(frame: pd.DataFrame) -> None:
    """Yaz yağışsızlığını sayıyla göster — sorunun fiziksel dayanağı budur."""
    ppt = frame["ppt"]
    monthly = ppt.groupby(ppt.index.month).mean()
    summer = monthly.loc[[7, 8]].mean()
    winter = monthly.loc[[12, 1, 2]].mean()
    print(f"\n    Aylık yağış iklimatolojisi (mm): "
          + " ".join(f"{m:02d}:{v:.0f}" for m, v in monthly.items()))
    print(f"    Yaz (Tem-Ağu) ortalaması {summer:.1f} mm, kış (Ara-Şub) {winter:.1f} mm "
          f"— {winter / max(summer, 0.1):.0f} kat fark.")
    print("    Yaz bitki örtüsünü o yazki yağış belirlemiyor; kışın biriken su belirliyor.")


def _best(rows):
    candidates = [
        r for r in rows
        if r.name not in ("iklimatoloji (eğitim ort.)", "kalıcılık (geçen yaz)")
        and np.isfinite(r.skill_vs_climatology) and np.isfinite(r.skill_vs_persistence)
        and r.skill_vs_climatology > 0 and r.skill_vs_persistence > 0
    ]
    return max(candidates, key=lambda r: r.skill_vs_climatology) if candidates else None


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _write_report(config, dataset, rows, learned, best, target) -> None:
    out = resolve(config["paths"]["reports"]) / "seasonal_forecast.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    parts = [
        "# Mevsimsel Öngörü — Kış Sonu Durumundan Yaz Stresi",
        "",
        "## Soru neden yeniden kuruldu",
        "",
        "İlk denemede \"SPI-3'ten 3 ay sonraki SPI-3\" soruldu ve beceri sıfır",
        "çıktı. Bu bir veri bulgusu değil, kötü kurulmuş bir soruydu: ay *t* için",
        "SPI-3 *t−2…t* penceresini toplar, *t+3* için *t+1…t+3*'ü — **iki pencere",
        "hiç kesişmez**, paylaşılacak bilgi yoktur.",
        "",
        "Fiziksel olarak anlamlı soru şudur: Akdeniz ikliminde yaz yağışsızdır,",
        "dolayısıyla yaz bitki örtüsünü belirleyen şey o yazki yağış değil,",
        "**kışın toprakta biriken sudur**. Öngörülebilirlik varsa oradadır.",
        "",
        "## Kurgu",
        "",
        f"- **Öngörücüler** ({dataset.predictor_season} sonunda bilinir): "
        f"{', '.join(dataset.predictors.columns)}",
        f"- **Hedef** ({dataset.target_season}): {dataset.target_name}",
        f"- **Yıl sayısı:** {len(dataset.target)} "
        f"({dataset.target.index.min()}–{dataset.target.index.max()})",
        "",
        "Öngörücü ve hedef aylarının kesişmediği kod içinde denetlenir; kesişselerdi",
        "hedeften öngörücüye bilgi sızar ve beceri yapay olarak yükselirdi.",
        "",
        "## Öngörücülerin hedefle ilişkisi",
        "",
        "```",
        dataset.describe(),
        "```",
        "",
        "## Beceri",
        "",
        "```",
        seasonal_skill_table(rows, learned, dataset),
        "```",
        "",
        "## Sonuç",
        "",
    ]

    if best is None:
        parts += [
            "**Hiçbir öngörücü her iki taban çizgisini birden geçemedi.**",
            "",
            "Yani kış sonu su durumu, bu havzada yaz stresini iklimatolojiden ve",
            "geçen yılın tekrarından daha iyi öngörmüyor. Fiziksel bağ makul olsa",
            "da öngörü değeri taşımıyor — bu, raporlanması gereken olumsuz bir",
            "sonuçtur ve modeli karmaşıklaştırarak 'düzeltilmemelidir'.",
        ]
    else:
        parts += [
            f"**En iyi öngörücü: `{best.name}`**",
            "",
            f"| Ölçüt | Değer |",
            "|---|---:|",
            f"| İklimatolojiye karşı beceri | {best.skill_vs_climatology:+.3f} |",
            f"| Kalıcılığa karşı beceri | {best.skill_vs_persistence:+.3f} |",
            f"| Test dönemi korelasyonu | {best.correlation:+.3f} |",
            f"| Test yılı sayısı | {best.n_test} |",
            "",
            "Bir öngörücünün işe yaradığını söyleyebilmek için **her iki** beceri",
            "skorunun da pozitif olması gerekir: iklimatolojiyi geçmek yetmez,",
            "geçen yılın tekrarını da geçmelidir.",
        ]

    parts += [
        "",
        "## Sınırlılıklar",
        "",
        "1. **Model kasten basit.** Tek değişkenli doğrusal regresyon. Amaç en iyi",
        "   tahmini bulmak değil, fiziksel bağın öngörü değeri taşıyıp taşımadığını",
        "   göstermek. Az sayıda yılla karmaşık model aşırı uyum üretir.",
        "2. **Hedef, etkinin dolaylı ölçüsüdür.** Toprak nemi verim değildir.",
        "3. **Dinamik iklim tahmini kullanılmadı.** ECMWF SEAS5 gibi ürünler",
        "   ufku gerçekten uzatabilir ama API anahtarı gerektirir.",
    ]
    out.write_text("\n".join(parts), encoding="utf-8")


def _figure(config, dataset, learned) -> None:
    """En güçlü öngörücü ile hedefin saçılım grafiği."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    viz = config["visualization"]
    correlations = {
        name: abs(pd.concat([dataset.predictors[name], dataset.target], axis=1)
                  .dropna().corr().iloc[0, 1])
        for name in dataset.predictors.columns
    }
    if not correlations:
        return
    name = max(correlations, key=correlations.get)

    joint = pd.concat([dataset.predictors[name].rename("x"), dataset.target.rename("y")],
                      axis=1).dropna()
    train_end = learned["train_span"][1]
    train = joint[joint.index <= train_end]
    test = joint[joint.index > train_end]

    fig, ax = plt.subplots(figsize=(8.5, 5.5), dpi=viz["dpi"])
    fig.patch.set_facecolor(viz["surface"])
    ax.set_facecolor(viz["surface"])

    ax.scatter(train["x"], train["y"], s=42, color="#2a78d6", edgecolor=viz["surface"],
               linewidth=1.2, label=f"eğitim ({learned['train_span'][0]}–{train_end})", zorder=3)
    ax.scatter(test["x"], test["y"], s=52, color="#eb6834", edgecolor=viz["surface"],
               linewidth=1.2, marker="D", label=f"test ({learned['test_span'][0]}–"
               f"{learned['test_span'][1]})", zorder=4)

    if name in learned["fits"]:
        fit = learned["fits"][name]
        xs = np.linspace(joint["x"].min(), joint["x"].max(), 50)
        ax.plot(xs, fit["slope"] * xs + fit["intercept"], color=viz["text_secondary"],
                lw=1.6, ls="--", zorder=2, label="eğitimden uyarlanan doğru")

    ax.set_xlabel(f"{name} (nisan sonunda bilinir)", fontsize=9.5, color=viz["text_secondary"])
    ax.set_ylabel(dataset.target_name, fontsize=9.5, color=viz["text_secondary"])
    ax.set_title(
        f"Kış sonu durumu ile yaz stresi ilişkisi — r = {correlations[name]:.3f}",
        loc="left", fontsize=12.5, color=viz["text_primary"], weight="bold", pad=10,
    )
    ax.grid(color=viz["gridline"], lw=0.7)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(viz["gridline"])
    ax.tick_params(colors=viz["text_muted"], labelsize=8.5)
    ax.legend(frameon=False, fontsize=9)

    out = resolve(config["paths"]["figures"]) / "seasonal_predictor.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight", facecolor=viz["surface"])
    plt.close(fig)
    print(f"\n[4] Görsel: {out.name}")


if __name__ == "__main__":
    raise SystemExit(main())
