"""Adım 10 — Kuraklık izleme ve tahmin.

Risk haritası "nerede yapısal olarak dayanıksız" sorusunu cevaplar; bu adım
"şu an ne oluyor" ve "üç ay sonra ne olabilir" sorularını ekler.

    RİSK = TEHLİKE (zamanla değişir) x DUYARLILIK (yapısal)
           ↑ bu adım                   ↑ Adım 4-5'teki AHP haritası

Kullanım:
    python -m scripts.step10_forecast --fetch      # 67 yıllık seriyi indir
    python -m scripts.step10_forecast              # SPI + tahmin + anomali
    python -m scripts.step10_forecast --year 2023  # anomali yılını değiştir

Çıktılar:
    outputs/reports/drought_forecast.md
    outputs/figures/spi_series.png
    outputs/figures/ndvi_anomaly_<yıl>.png
"""

from __future__ import annotations

import argparse

import numpy as np

from src.config import load_config
from src.drought_index import drought_events, spi
from src.fetch.climate_series import (
    annual_summary,
    fetch_basin_climate_series,
    load_basin_climate_series,
)
from src.fetch.common import resolve
from src.forecast import run_benchmark, skill_table
from src.grid import build_grid, read_grid_aligned

SPI_SCALES = (3, 6, 12)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Kuraklık izleme ve tahmin (Adım 10)")
    parser.add_argument("--config", default=None)
    parser.add_argument("--fetch", action="store_true", help="İklim serisini indir/yenile")
    parser.add_argument("--year", type=int, default=None, help="Anomali hesaplanacak yıl")
    parser.add_argument("--train-fraction", type=float, default=0.7)
    parser.add_argument("--skip-anomaly", action="store_true")
    args = parser.parse_args(argv)

    config = load_config(args.config)

    print("=" * 74)
    print("ADIM 10 — KURAKLIK İZLEME VE TAHMİN")
    print("=" * 74)

    if args.fetch:
        fetch_basin_climate_series(config, overwrite=True)

    frame = load_basin_climate_series(config)
    precipitation = frame["ppt"].dropna()
    span = f"{precipitation.index[0]:%Y-%m} - {precipitation.index[-1]:%Y-%m}"
    print(f"\n[1] Yağış serisi: {len(precipitation)} ay ({span}), "
          f"{precipitation.index.year.nunique()} yıl")

    annual = annual_summary(frame)
    driest = annual.nsmallest(5, "toplam_mm")
    print("    En kurak 5 yıl:")
    for timestamp, row in driest.iterrows():
        print(f"      {timestamp.year}  {row['toplam_mm']:7.1f} mm  "
              f"(normalin %{100 * row['normale_oran']:.0f}'i)")

    # --- SPI ---------------------------------------------------------------
    print("\n[2] SPI (McKee ve ark. 1993)")
    results = {}
    for scale in SPI_SCALES:
        results[scale] = spi(precipitation, scale=scale)
        print("\n" + _indent(results[scale].summary()))

    _cross_check_pdsi(frame, results)

    print("\n[3] En şiddetli kuraklık olayları (SPI-12 <= -1)")
    events = drought_events(results[12].values, threshold=-1.0)
    if events.empty:
        print("    kayda değer olay yok")
    else:
        for _, event in events.head(5).iterrows():
            print(f"    {event['başlangıç']:%Y-%m} - {event['bitiş']:%Y-%m}  "
                  f"{event['süre_ay']:>3} ay  en düşük SPI {event['en_düşük_spi']:+.2f}  "
                  f"şiddet {event['şiddet']:+.1f}")

    # --- Tahmin ------------------------------------------------------------
    print("\n[4] Tahmin becerisi — taban çizgilerine karşı")
    print("    Kural: bir yöntem kalıcılığı geçemiyorsa hiçbir şey katmıyordur.")
    rows, learned = run_benchmark(results[3].values, train_fraction=args.train_fraction)
    print("\n" + _indent(skill_table(rows, learned)))

    current = _current_state(results)
    print("\n[5] Serinin sonundaki durum")
    for line in current:
        print(f"    {line}")

    # --- Mekânsal anomali --------------------------------------------------
    anomaly = None
    if not args.skip_anomaly:
        anomaly = _spatial_anomaly(config, args.year)

    _write_report(config, precipitation, results, events, rows, learned, current, anomaly)
    _figures(config, results, anomaly)

    print("\nAdım 10 tamamlandı. Rapor: outputs/reports/drought_forecast.md")
    return 0


def _cross_check_pdsi(frame, results) -> None:
    """Kendi SPI hesabımızı, bağımsız bir kuraklık indeksiyle sınar."""
    if "pdsi" not in frame.columns:
        return
    import pandas as pd

    joint = pd.concat([results[12].values.rename("spi12"), frame["pdsi"]], axis=1).dropna()
    if len(joint) < 120:
        return
    corr = float(joint.corr().iloc[0, 1])
    print(f"\n    Çapraz kontrol — SPI-12 ile TerraClimate PDSI: r = {corr:.3f}")
    print("    (PDSI bağımsız bir formülasyondur; yüksek korelasyon SPI hesabının")
    print("     doğru kurulduğunu destekler, ikisi aynı olguyu farklı yoldan ölçer)")


def _current_state(results) -> list[str]:
    from src.drought_index import classify_spi

    lines = []
    for scale, result in results.items():
        series = result.values.dropna()
        if series.empty:
            continue
        value = float(series.iloc[-1])
        lines.append(
            f"SPI-{scale:<2} = {value:+.2f}  ({classify_spi(value)})   "
            f"[{series.index[-1]:%Y-%m}]"
        )
    return lines


def _spatial_anomaly(config, year: int | None):
    from src.monitor import anomaly_by_landcover, anomaly_by_risk_class, ndvi_anomaly

    year = year or max(config["periods"]["reference_years"])
    grid = build_grid(config)

    print(f"\n[6] Mekânsal NDVI anomalisi — {year}")
    try:
        result = ndvi_anomaly(config, grid, year)
    except (FileNotFoundError, ValueError) as exc:
        print(f"    atlandı: {exc}")
        return None

    print("\n" + _indent(result.summary()))

    print("\n    Arazi örtüsüne göre ortalama anomali:")
    for name, mean_z, count in anomaly_by_landcover(config, grid, result):
        print(f"      {name:<30}{mean_z:+.3f}  ({count:,} piksel)")

    class_path = resolve(config["paths"]["data_processed"]) / f"risk_class_{config.scenario}.tif"
    if class_path.exists():
        from src.grid import read_grid_aligned

        classes = read_grid_aligned(class_path, grid)
        rows = anomaly_by_risk_class(config, grid, result, classes)
        labels = config["classification"]["labels"]
        print("\n    RİSK HARİTASININ OPERASYONEL SINAMASI")
        print("    Beklenti: risk sınıfı arttıkça anomali daha negatif olmalı.")
        for code, mean_z, count in rows:
            print(f"      {code} — {labels[code]:<12}{mean_z:+.3f}  ({count:,} piksel)")

        monotone = all(rows[i][1] >= rows[i + 1][1] for i in range(len(rows) - 1))
        extremes = rows[-1][1] < rows[0][1]
        risk_path = resolve(config["paths"]["data_processed"]) / f"risk_index_{config.scenario}.tif"
        rho = float("nan")
        if risk_path.exists():
            from src.validate import rank_correlation

            risk = read_grid_aligned(risk_path, grid).astype("float32")
            risk = np.where(risk == np.float32(config.nodata), np.nan, risk)
            rho = rank_correlation(risk, result.z_score)

        print(f"      Monotonluk       : {'EVET' if monotone else 'HAYIR'}")
        print(f"      Uçlar doğru yönde: {'EVET' if extremes else 'HAYIR'} "
              f"(sınıf 5 {rows[-1][1]:+.3f} < sınıf 1 {rows[0][1]:+.3f})")
        print(f"      Spearman ρ (risk indeksi ↔ anomali): {rho:+.4f}")
        print("      Yorum: risk haritası 6 yıllık ORTALAMAYA dayanan yapısal bir")
        print("      indekstir; tek bir yılın anomalisi onun zayıf bir sınamasıdır.")
        result = (result, rows, monotone, extremes, rho)
    return result


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _write_report(config, precipitation, results, events, rows, learned, current, anomaly) -> None:
    out = resolve(config["paths"]["reports"]) / "drought_forecast.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    parts = [
        "# Kuraklık İzleme ve Tahmin",
        "",
        f"**Bölge:** {config['aoi']['name']}  ",
        f"**Yağış serisi:** TerraClimate, {precipitation.index[0]:%Y-%m} - "
        f"{precipitation.index[-1]:%Y-%m} ({precipitation.index.year.nunique()} yıl)",
        "",
        "## Bu modül ne yapar, ne yapmaz",
        "",
        "AHP risk haritası *yapısal duyarlılığı* gösterir — nerede kronik olarak",
        "dayanıksız. Bu modül ona **zaman boyutu** ekler:",
        "",
        "```",
        "RİSK = TEHLİKE (zamanla değişir) x DUYARLILIK (yapısal)",
        "       ↑ bu modül                  ↑ AHP haritası",
        "```",
        "",
        "**Yapmadığı:** dinamik mevsimsel iklim tahmini kullanmaz. ECMWF SEAS5",
        "gibi ürünler kayıt/API anahtarı gerektirdiği için projenin \"anahtarsız\"",
        "kısıtını kırardı. Buradaki tahmin, serinin kendi otokorelasyonuna",
        "dayanan istatistiksel bir taban çizgisidir.",
        "",
        "## 1. SPI",
        "",
    ]
    for scale, result in results.items():
        parts += ["```", result.summary(), "```", ""]

    parts += ["## 2. En şiddetli kuraklık olayları (SPI-12 ≤ −1)", ""]
    if events.empty:
        parts.append("Kayda değer olay yok.")
    else:
        parts += ["| Başlangıç | Bitiş | Süre (ay) | En düşük SPI | Şiddet |", "|---|---|---:|---:|---:|"]
        for _, event in events.head(8).iterrows():
            parts.append(
                f"| {event['başlangıç']:%Y-%m} | {event['bitiş']:%Y-%m} | "
                f"{event['süre_ay']} | {event['en_düşük_spi']:+.2f} | {event['şiddet']:+.1f} |"
            )

    parts += [
        "",
        "## 3. Tahmin becerisi",
        "",
        "**Neden taban çizgisi şart.** Kuraklık güçlü otokorelasyonludur; \"üç ay",
        "sonra da bugünkü gibi olacak\" demek şaşırtıcı derecede iyi çalışır. Bir",
        "yöntemin becerisi mutlak hatayla değil, taban çizgisine göre kazancıyla",
        "ölçülür. Beceri skoru 0'ın altındaysa yöntem referanstan kötüdür.",
        "",
        "**Neden kronolojik bölme.** Zaman serisinde rastgele eğitim/test ayrımı",
        "veri sızıntısıdır: komşu aylar birbirine benzer, model ezberler, skor",
        "gerçekte olmayan bir başarı gösterir.",
        "",
        "```",
        skill_table(rows, learned),
        "```",
        "",
        "## 4. Serinin sonundaki durum",
        "",
    ] + [f"- `{line}`" for line in current]

    if anomaly is not None:
        if isinstance(anomaly, tuple):
            result, class_rows, monotone, extremes, rho = anomaly
        else:
            result, class_rows, monotone, extremes, rho = anomaly, None, None, None, None
        parts += ["", "## 5. Mekânsal NDVI anomalisi", "", "```", result.summary(), "```"]
        if class_rows:
            labels = config["classification"]["labels"]
            parts += [
                "",
                "### Risk haritasının operasyonel sınaması",
                "",
                "Yüksek riskli sınıflandırılan alanlar, kurak bir yılda gerçekten daha",
                "fazla mı etkileniyor?",
                "",
                "| Risk sınıfı | Ortalama NDVI anomalisi (z) | Piksel |",
                "|---|---:|---:|",
            ]
            for code, mean_z, count in class_rows:
                parts.append(f"| {code} — {labels[code]} | {mean_z:+.3f} | {count:,} |")
            parts += [
                "",
                f"- Beş sınıf boyunca monotonluk: **{'evet' if monotone else 'HAYIR'}**",
                f"- Uçlar doğru yönde (sınıf 5 < sınıf 1): "
                f"**{'evet' if extremes else 'hayır'}**",
                f"- Risk indeksi ile anomali arasında Spearman ρ = **{rho:+.4f}**",
                "",
                "**Yorum.** Uçlar beklenen yönde ama sıralama monoton değil ve",
                "korelasyon zayıf. Bu, ayarlanarak geçirilecek bir sonuç değil;",
                "iki katmanın farklı şeyleri ölçtüğünü gösteriyor:",
                "",
                "- Risk haritası 6 yıllık ORTALAMAYA dayanan **yapısal** bir indekstir",
                "  — \"burası kronik olarak dayanıksız\".",
                "- Anomali ise tek bir yılın kendi geçmişine göre sapmasıdır",
                "  — \"bu yıl normalinden ne kadar saptı\".",
                "",
                "Yapısal olarak kurak bir alan zaten *her yıl* kuraktır; kendi",
                "normaline göre sapması büyük olmak zorunda değildir. Dolayısıyla",
                "tek yılın anomalisi, yapısal risk haritasının zayıf bir sınamasıdır.",
                "Güçlü sınama, birden çok kurak yılın anomalilerinin ortalamasıyla",
                "ya da doğrudan verim verisiyle yapılır (bkz. Sınırlılıklar).",
            ]

    parts += [
        "",
        "## Sınırlılıklar",
        "",
        "1. **Tahmin istatistikseldir, dinamik değildir.** Atmosfer modeli yok;",
        "   yalnızca serinin geçmiş davranışı kullanılıyor.",
        "2. **Mekânsal anomalinin taban çizgisi 6 yıl.** Sentinel-2 arşivi kısa;",
        "   z-skorunun standart sapması az örnekten kestiriliyor. SPI'ın 67 yıllık",
        "   tabanı çok daha sağlamdır.",
        "3. **Havza ölçeğinde tahmin.** TerraClimate ~4 km; bu çözünürlükte piksel",
        "   bazlı tahmin, veride olmayan bir kesinlik iddiası olurdu.",
    ]

    out.write_text("\n".join(parts), encoding="utf-8")


def _figures(config, results, anomaly) -> None:
    from src.visualize_forecast import plot_anomaly_map, plot_spi_series

    print("\n[7] Görseller")
    print(f"  {plot_spi_series(config, results).name}")
    if anomaly is not None:
        result = anomaly[0] if isinstance(anomaly, tuple) else anomaly
        print(f"  {plot_anomaly_map(config, build_grid(config), result).name}")


if __name__ == "__main__":
    raise SystemExit(main())
