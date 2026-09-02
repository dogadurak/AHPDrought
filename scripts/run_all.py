"""Bütün analiz hattını tek komutla çalıştırır.

NEDEN VAR: hat on altı adım ve doğru sırayla çalışması gerekiyor — kriter
raster'ları grid'den, risk haritası kriterlerden, doğrulama risk haritasından
besleniyor. Adımları tek tek yazmak, projeyi ilk kez çalıştıran birinin
karşılaştığı ilk engel. Bu betik sırayı bilir.

VARSAYILAN OLARAK AĞA ÇIKMAZ. İndirme adımları (~2,5 saat) `--with-fetch` ile
açılır; onlarsız betik yalnızca `data/interim/` altında hazır duran katmanlarla
çalışır. Sebep: indirme bir kez yapılır, analiz onlarca kez.

    python -m scripts.run_all                 # analiz adımları (ağsız)
    python -m scripts.run_all --with-fetch    # indirme dahil, sıfırdan
    python -m scripts.run_all --from step04   # risk haritasından itibaren
    python -m scripts.run_all --only step04,step07
    python -m scripts.run_all --dry-run       # ne çalışacağını göster
    python -m scripts.run_all --scenario flat_riskier

Bir adım hata verirse hat orada durur — sonraki adım zaten bozuk girdiyle
çalışacaktı. `--keep-going` bunu gevşetir; sonda hangi adımın düştüğü tablo
hâlinde yazılır.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass, field

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Step:
    """Hattın bir adımı.

    `network`: dış servise bağlanır, uzun sürer, `--with-fetch` ister.
    `scenario`: `--scenario` bayrağını kabul eder (hepsi kabul etmiyor).
    `extra`: adıma özel sabit bayraklar.
    """

    name: str
    module: str
    title: str
    network: bool = False
    scenario: bool = False
    extra: list[str] = field(default_factory=list)


# Sıra önemli: her adım kendinden öncekinin çıktısını okur.
PIPELINE: list[Step] = [
    Step("step01", "scripts.step01_define_grid", "AOI, ortak grid, AHP tutarlılık kontrolü", scenario=True),
    Step("step02", "scripts.step02_fetch_data", "Ham katmanları indir (~1,5 sa)", network=True),
    Step("step03", "scripts.step03_build_criteria", "Kriter raster'ları", scenario=True),
    Step("step04", "scripts.step04_risk_map", "AHP çakıştırma, duyarlılık, risk haritası", scenario=True),
    Step("step06", "scripts.step06_ndvi_timeseries", "NDVI animasyonu ve parsel eğrileri"),
    Step("step07", "scripts.step07_validate", "Doğrulama raporu", scenario=True),
    Step("step10fetch", "scripts.step10_forecast", "68 yıllık iklim serisini indir (~25 dk)", network=True, extra=["--fetch"]),
    Step("step10", "scripts.step10_forecast", "Kuraklık izleme ve tahmin"),
    Step("step11", "scripts.step11_operational", "Çok yıllı operasyonel sınama"),
    Step("step12", "scripts.step12_seasonal", "Mevsimsel öngörü"),
    Step("step13fetch", "scripts.step13_historical", "Landsat 5 arşivini indir (~90 dk)", network=True, extra=["--fetch"]),
    Step("step13", "scripts.step13_historical", "Gerçek kuraklıklarda sınama (1985–2011)", scenario=True),
    Step("step14", "scripts.step14_machine_learning_test", "Fiziksel taban çizgisi (Random Forest)", scenario=True),
    Step("step15", "scripts.step15_resilience_gap", "Fiziksel-gözlemsel uyumsuzluk haritası", scenario=True),
    Step("step17", "scripts.step17_low_variance_hypothesis", "Düşük değişkenlik hipotezinin sınanması", scenario=True),
    Step("step18", "scripts.step18_historical_decoupling_trend", "Tarihsel ayrışma eğilimi", scenario=True),
    # Adım 16, Adım 14'ün eğittiği modeli KULLANIR; sırası bu yüzden 14'ten sonra.
    # Çıktıları `*_rf_*` adlarıyla ayrıdır, AHP haritasının üstüne yazmaz.
    Step("step16", "scripts.step16_rf_risk_map", "RF risk haritası (AHP ile karşılaştırma)", scenario=True),
    Step("evi", "scripts.compare_vegetation_index", "NDVI / EVI karşılaştırması"),
    Step("export", "scripts.export_web_data", "Arayüzlerin okuduğu özet verisi"),
]

BY_NAME = {s.name: s for s in PIPELINE}


def _select(args) -> list[Step]:
    """Bayraklara göre çalıştırılacak adımları seçer."""
    steps = list(PIPELINE)

    if args.only:
        wanted = [w.strip() for w in args.only.split(",") if w.strip()]
        unknown = [w for w in wanted if w not in BY_NAME]
        if unknown:
            sys.exit(f"Bilinmeyen adım: {', '.join(unknown)}\nGeçerli: {', '.join(BY_NAME)}")
        return [BY_NAME[w] for w in wanted]

    if args.start:
        if args.start not in BY_NAME:
            sys.exit(f"Bilinmeyen adım: {args.start}\nGeçerli: {', '.join(BY_NAME)}")
        names = [s.name for s in steps]
        steps = steps[names.index(args.start):]

    if not args.with_fetch:
        steps = [s for s in steps if not s.network]

    return steps


def _command(step: Step, args) -> list[str]:
    cmd = [sys.executable, "-m", step.module, *step.extra]
    if step.scenario and args.scenario:
        cmd += ["--scenario", args.scenario]
    return cmd


def main() -> int:
    # Konsol kod sayfası dar olabilir (Windows cp1254/cp437). Tek bir
    # karakter yüzünden saatlerce süren bir hattın çökmesi kabul edilemez.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(
        description="AHP kuraklık risk hattını sırayla çalıştırır.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Adımlar: " + ", ".join(BY_NAME),
    )
    ap.add_argument("--with-fetch", action="store_true", help="indirme adımlarını da çalıştır (~2,5 sa)")
    ap.add_argument("--from", dest="start", metavar="ADIM", help="bu adımdan itibaren çalıştır")
    ap.add_argument("--only", metavar="ADIM[,ADIM]", help="yalnızca bu adımları çalıştır")
    ap.add_argument("--scenario", metavar="AD", help="senaryo adı (kabul eden adımlara geçilir)")
    ap.add_argument("--keep-going", action="store_true", help="bir adım düşse de devam et")
    ap.add_argument("--dry-run", action="store_true", help="çalıştırma, yalnızca planı yaz")
    args = ap.parse_args()

    steps = _select(args)
    if not steps:
        print("Çalıştırılacak adım kalmadı.")
        return 0

    print(f"{len(steps)} adım · çalışma dizini {PROJECT_ROOT}")
    if not args.with_fetch and any(s.network for s in PIPELINE):
        print("İndirme adımları atlandı (--with-fetch ile açılır).")
    print()

    results: list[tuple[Step, str, float]] = []
    failed = False

    for i, step in enumerate(steps, 1):
        cmd = _command(step, args)
        head = f"[{i}/{len(steps)}] {step.name} — {step.title}"
        if args.dry_run:
            print(f"{head}\n      {' '.join(cmd[1:])}")
            continue

        print(f"{head}\n{'-' * min(len(head), 72)}")
        t0 = time.perf_counter()
        code = subprocess.run(cmd, cwd=PROJECT_ROOT).returncode
        dt = time.perf_counter() - t0
        results.append((step, "tamam" if code == 0 else f"HATA ({code})", dt))
        print(f"      {results[-1][1]} · {dt:.1f} sn\n")

        if code != 0:
            failed = True
            if not args.keep_going:
                print(f"{step.name} düştü, hat durduruldu. Devam için --keep-going.")
                break

    if args.dry_run:
        print("\n(--dry-run: hiçbir şey çalıştırılmadı)")
        return 0

    print("Özet")
    print("-" * 72)
    for step, status, dt in results:
        print(f"  {step.name:<12} {status:<12} {dt:>8.1f} sn   {step.title}")
    print(f"\nToplam {sum(r[2] for r in results):.1f} sn")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
