"""Grup AHP anketi — form üretme ve uzman yanıtlarını birleştirme.

Kullanım:
    # 1. Her uzman için boş form üret
    python -m scripts.ahp_survey template --out surveys/ --experts 5

    # 2. Formlar doldurulduktan sonra birleştir
    python -m scripts.ahp_survey aggregate surveys/*.csv

    # 3. Tutarsız uzmanları da dahil ederek bak (karşılaştırma için)
    python -m scripts.ahp_survey aggregate surveys/*.csv --keep-inconsistent

Çıktı: uzman başına CR tablosu, birleşik ağırlıklar ve config.yaml'a
yapıştırılabilir matris.
"""

from __future__ import annotations

import argparse
import glob
from pathlib import Path

from src.ahp_survey import group_report, read_response, write_questionnaire
from src.config import PROJECT_ROOT, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grup AHP anketi araçları")
    parser.add_argument("--config", default=None)
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template", help="Boş anket formu üret")
    template.add_argument("--out", default="surveys", help="Çıktı klasörü")
    template.add_argument("--experts", type=int, default=1, help="Kaç uzman formu üretilsin")

    aggregate = sub.add_parser("aggregate", help="Doldurulmuş formları birleştir")
    aggregate.add_argument("paths", nargs="+", help="CSV dosyaları (glob desteklenir)")
    aggregate.add_argument("--keep-inconsistent", action="store_true",
                           help="CR eşiğini aşan uzmanları da birleştirmeye dahil et")
    aggregate.add_argument("--report", default="outputs/reports/ahp_survey.md")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    if args.command == "template":
        return _template(config, args)
    return _aggregate(config, args)


def _template(config, args) -> int:
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir

    n = len(config.criteria_order)
    print(f"{n} kriter -> {n * (n - 1) // 2} ikili karşılaştırma sorusu\n")

    for i in range(1, args.experts + 1):
        write_questionnaire(config, out_dir / f"uzman_{i:02d}.csv", respondent=f"uzman_{i:02d}")

    print(f"\nFormlar {out_dir} altında. Doldurduktan sonra:")
    print(f"  python -m scripts.ahp_survey aggregate {out_dir.name}/*.csv")
    return 0


def _aggregate(config, args) -> int:
    paths: list[Path] = []
    for pattern in args.paths:
        matched = [Path(p) for p in glob.glob(pattern)]
        paths.extend(matched or [Path(pattern)])

    missing = [p for p in paths if not p.exists()]
    if missing:
        raise SystemExit(f"Bulunamayan dosya: {missing}")

    print("=" * 68)
    print("GRUP AHP — UZMAN ANKETİ BİRLEŞTİRME")
    print(f"{len(paths)} form")
    print("=" * 68)

    respondents = []
    for path in sorted(paths):
        try:
            respondents.append(read_response(config, path))
        except ValueError as exc:
            print(f"  {path.name}: OKUNAMADI — {exc}")

    if not respondents:
        raise SystemExit("Hiçbir form okunamadı.")

    result, report = group_report(
        config, respondents, exclude_inconsistent=not args.keep_inconsistent
    )
    print("\n" + report)

    out = Path(args.report)
    if not out.is_absolute():
        out = PROJECT_ROOT / out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        f"# Grup AHP anketi sonucu\n\n```\n{report}\n```\n", encoding="utf-8"
    )
    print(f"\nRapor: {out.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
