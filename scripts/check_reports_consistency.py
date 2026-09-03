"""README ve arayüzdeki sayıların rapor dosyalarıyla tuttuğunu sınar.

NEDEN VAR: bu projede tam olarak şu oldu — hattın bir adımı değişti, raporlar
ve raster yenilendi, ama README'deki sayılar eski çalıştırmadan kaldı. Aynı
büyüklüğün üç farklı değeri aynı belgede yan yana durdu ve kimse fark etmedi.
Metni okuyan bir insan bunu yakalayamaz; kaynağıyla karşılaştıran bir betik
yakalar.

NASIL ÇALIŞIR: her ölçüm, üreten rapor dosyasından bir düzenli ifadeyle
okunur, Türkçe yazımına (virgüllü ondalık, U+2212 eksi) çevrilir ve belgede
aranır. Yuvarlama farkını tolere etmek için 2-4 ondalıklı yazımların hepsi
kabul edilir; biri geçerse ölçüm tutuyor sayılır.

    python -m scripts.check_reports_consistency

Çıkış kodu 0: belgeler raporlarla tutuyor. 1: en az bir sayı sapmış.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORTS = PROJECT_ROOT / "outputs" / "reports"

# Sayıların görünmesi gereken belgeler.
DOCUMENTS = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "web-app" / "src" / "App.jsx",
)


@dataclass(frozen=True)
class Check:
    """Bir ölçümün kaynağı ve nasıl bulunacağı.

    `pattern` raporda sayıyı yakalar; `scale` yüzdeye çevirmek gerekiyorsa
    100 olur; `must_appear` False ise sayı belgelerde geçmek zorunda değildir
    (yalnızca raporda bulunabilirliği sınanır).
    """

    label: str
    report: str
    pattern: str
    scale: float = 1.0
    percent: bool = False
    must_appear: bool = True


CHECKS = (
    Check("Tutarlılık oranı (CR)", "ahp_steep_riskier.md", r"CR = (\d+\.\d+)"),
    Check("k-means uyumu", "ahp_steep_riskier.md", r"\*\*%(\d+\.\d+)\*\* oranında", percent=True),
    Check("En duyarlı senaryo sınıf uyumu", "ahp_steep_riskier.md",
          r"En duyarlı senaryo: \S+ — sınıf uyumu %(\d+\.\d+)", percent=True),
    Check("Senaryo dayanıklılığı", "validation_report.md",
          r"Aynı sınıfta kalan piksel \| %(\d+\.\d+)", percent=True),
    Check("ET/PET sıra korelasyonu", "validation_report.md",
          r"Spearman ρ = \*\*(-?\d+\.\d+)\*\*"),
    Check("Landsat kurak yıl ρ", "historical_test_ndvi.md",
          r"Kurak yıllar\s+\(n=\d+\): ortalama r = ([+-]\d+\.\d+)"),
    Check("ET/PET kurak yıl ρ", "historical_test_et.md",
          r"Kurak yıllar\s+\(n=\d+\): ortalama r = ([+-]\d+\.\d+)"),
    Check("Yüzey sıcaklığı kurak yıl ρ", "historical_test_lst.md",
          r"Kurak yıllar\s+\(n=\d+\): ortalama r = ([+-]\d+\.\d+)"),
    Check("Random Forest ortalama R²", "ml_baseline_physical.md",
          r"\*\*ortalama\*\* \| \*\*([+-]\d+\.\d+)\*\*"),
    Check("Hipotez sınaması alt küme ρ", "low_variance_hypothesis.md",
          r"\| Alt küme \| \d+ \| \*\*([+-]\d+\.\d+)\*\*"),
    Check("Tarihsel ayrışma eğimi", "historical_decoupling.md",
          r"eğim \*\*([+-]\d+\.\d+)/yıl\*\*"),
    Check("NDVI risk haritasının ET/PET uyumu", "vegetation_index_comparison.md",
          r"NDVI\s+ham katman.*?risk haritası .? = (-?\d+\.\d+)"),
    Check("2001 kuraklığının korelasyonu", "historical_decoupling.md",
          r"\| 2001 \| KURAK \| ([+-]\d+\.\d+) \|"),
)


def _tr(value: float, digits: int, *, percent: bool, signed: bool) -> str:
    """Sayıyı belgelerdeki yazımına çevirir: virgüllü ondalık, U+2212 eksi."""
    text = f"{abs(value):.{digits}f}".replace(".", ",")
    if percent:
        return f"%{text}"
    if signed and value > 0:
        return f"+{text}"
    if value < 0:
        return f"−{text}"  # düz tire değil, matematiksel eksi
    return text


def _candidates(value: float, *, percent: bool) -> list[str]:
    """Kabul edilebilir yazımlar — yuvarlama farkı hata sayılmasın."""
    out: list[str] = []
    for digits in (4, 3, 2, 1):
        for signed in (False, True):
            out.append(_tr(value, digits, percent=percent, signed=signed))
    # yinelenenleri koru, sıra önemsiz
    return list(dict.fromkeys(out))


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    docs = {}
    for path in DOCUMENTS:
        if not path.exists():
            print(f"UYARI: {path.relative_to(PROJECT_ROOT)} yok, atlandı.")
            continue
        docs[path] = path.read_text(encoding="utf-8")

    problems: list[str] = []
    checked = 0

    for check in CHECKS:
        report = REPORTS / check.report
        if not report.exists():
            problems.append(f"{check.label}: {check.report} yok — önce ilgili adımı çalıştırın")
            continue

        text = report.read_text(encoding="utf-8")
        match = re.search(check.pattern, text)
        if not match:
            problems.append(f"{check.label}: {check.report} içinde ölçüm bulunamadı")
            continue

        value = float(match.group(1)) * check.scale
        checked += 1
        if not check.must_appear:
            continue

        forms = _candidates(value, percent=check.percent)
        hit = {p.name for p, body in docs.items() if any(f in body for f in forms)}
        if not hit:
            problems.append(
                f"{check.label}: raporda {forms[0]} — hiçbir belgede geçmiyor "
                f"({check.report})"
            )

    print(f"{checked} ölçüm raporlardan okundu, {len(DOCUMENTS)} belgede arandı.")
    if problems:
        print(f"\n{len(problems)} sapma:")
        for p in problems:
            print(f"  - {p}")
        print("\nBelgelerdeki sayı, üreten raporla aynı olmalı. Ya belgeyi güncelleyin")
        print("ya da ilgili adımı yeniden çalıştırın.")
        return 1

    print("Belgelerdeki bütün ölçümler kaynak raporlarıyla tutuyor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
