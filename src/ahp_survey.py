"""Grup AHP — uzman anketiyle ikili karşılaştırma matrisi kurma araçları.

`config.yaml`'daki matris yazar tarafından, literatürdeki sıralamaya dayanarak
kurulmuş bir başlangıç setidir. Akademik bir çalışmada matrisin **alan
uzmanlarına yaptırılan anketle** oluşturulması beklenir. Bu modül o anketin
altyapısını sağlar:

    1. `write_questionnaire()`  — n(n−1)/2 soruluk CSV formu üretir
    2. `read_response()`        — doldurulmuş formu matrise çevirir
    3. `aggregate()`            — birden çok uzmanın matrisini birleştirir
    4. `group_report()`         — uzman başına CR ve grup sonucu raporlar

**Anketin kendisini yapmak insan işidir** — bu modül formu üretir ve
cevapları doğru şekilde birleştirir, uzman görüşünün yerine geçmez.

## Neden geometrik ortalama?

Bireysel yargıların birleştirilmesinde (AIJ — aggregation of individual
judgements) **geometrik** ortalama kullanılır, aritmetik değil. Gerekçe:
AHP matrisi karşılıklıdır (a_ji = 1/a_ij) ve bu özellik yalnızca geometrik
ortalamada korunur.

    İki uzman a_ij için 3 ve 1/3 demişse:
      geometrik: √(3 · 1/3) = 1        -> "eşit önemde", doğru
      aritmetik: (3 + 1/3)/2 = 1.67    -> i'yi kayırır, YANLIŞ

Aritmetik ortalama ayrıca a_ij ve a_ji'yi ayrı ayrı ortalamak zorunda kalır
ve sonuçta çarpımları 1 etmez, yani ortaya geçerli bir AHP matrisi çıkmaz.

Kaynak: Aczél, J. & Saaty, T. L. (1983). Procedures for synthesizing ratio
judgements. *Journal of Mathematical Psychology*, 27(1), 93–102.
"""

from __future__ import annotations

import csv
import itertools
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .ahp import AHPResult, solve_ahp
from .config import Config

# Saaty 1-9 ölçeğinin sözlü karşılıkları (form başlığına yazılır).
SAATY_SCALE = {
    1: "eşit derecede önemli",
    2: "eşit ile biraz daha önemli arası",
    3: "biraz daha önemli",
    4: "biraz ile belirgin daha önemli arası",
    5: "belirgin şekilde daha önemli",
    6: "belirgin ile çok daha önemli arası",
    7: "çok daha önemli",
    8: "çok ile aşırı daha önemli arası",
    9: "aşırı derecede daha önemli",
}


@dataclass(frozen=True)
class RespondentResult:
    """Tek bir uzmanın yanıtından çıkan sonuç."""

    name: str
    matrix: np.ndarray
    result: AHPResult | None
    consistency_ratio: float
    accepted: bool
    note: str = ""


def write_questionnaire(config: Config, out_path: str | Path, *, respondent: str = "") -> Path:
    """Uzmana verilecek boş anket formunu CSV olarak yazar.

    Her satır bir ikili karşılaştırmadır. Uzman `cevap` sütununa **işaretli**
    bir Saaty değeri yazar:

        +5  -> A kriteri B'den 'belirgin şekilde daha önemli'
         1  -> ikisi eşit derecede önemli
        -3  -> B kriteri A'dan 'biraz daha önemli'

    Tek sütun kullanılması bilinçlidir: uzmandan hem a_ij hem a_ji istemek,
    ikisinin çarpımının 1 etmediği tutarsız formlar üretir.
    """
    names = config.criteria_order
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8-sig", newline="") as fh:
        # Açıklama satırları csv.writer'dan GEÇİRİLMEZ: içlerinde virgül ve
        # kesme işareti olduğu için tırnaklanır ve formu açan uzman tırnaklarla
        # dolu bir metin görür. Doğrudan yazılıyorlar.
        comments = [
            "# AHP ikili karşılaştırma anketi",
            f"# Uzman: {respondent or '(adınızı yazın)'}",
            "#",
            "# Soru: TARIMSAL KURAKLIK RİSKİNİ belirlemede A mı B mi daha etkilidir?",
            "# 'cevap' sütununa işaretli bir Saaty değeri yazın:",
        ]
        comments += [
            f"#   {value:+d} = A; B'den {label}" if value > 1 else f"#    {value} = {label}"
            for value, label in SAATY_SCALE.items()
        ]
        comments += [
            "#   Negatif değer B'nin daha önemli olduğu anlamına gelir (ör. -5)",
            "#",
        ]
        fh.write("\n".join(comments) + "\n\n")

        writer = csv.writer(fh)
        writer.writerow(["no", "A_kod", "A_aciklama", "B_kod", "B_aciklama", "cevap"])

        for index, (a, b) in enumerate(itertools.combinations(names, 2), start=1):
            writer.writerow([
                index, a, config.criterion(a)["label"], b, config.criterion(b)["label"], "",
            ])

    total = len(names) * (len(names) - 1) // 2
    print(f"  Anket yazıldı: {out.name} ({total} soru, {len(names)} kriter)")
    return out


def read_response(config: Config, path: str | Path, *, name: str | None = None) -> RespondentResult:
    """Doldurulmuş anket formunu ikili karşılaştırma matrisine çevirir."""
    names = config.criteria_order
    index_of = {crit: i for i, crit in enumerate(names)}
    matrix = np.eye(len(names))

    path = Path(path)
    answered: set[tuple[str, str]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(_data_rows(fh)):
            a, b, raw = row.get("A_kod"), row.get("B_kod"), (row.get("cevap") or "").strip()
            if not a or not b:
                continue
            if a not in index_of or b not in index_of:
                raise ValueError(f"{path.name}: bilinmeyen kriter '{a}' veya '{b}'")
            if not raw:
                raise ValueError(f"{path.name}: '{a}' vs '{b}' cevaplanmamış")

            value = _to_saaty(raw, path.name, a, b)
            i, j = index_of[a], index_of[b]
            matrix[i, j] = value
            matrix[j, i] = 1.0 / value
            answered.add((a, b))

    expected = set(itertools.combinations(names, 2))
    missing = expected - answered
    if missing:
        raise ValueError(f"{path.name}: {len(missing)} karşılaştırma eksik, ilk örnek: {sorted(missing)[0]}")

    max_cr = float(config["ahp"]["consistency"]["max_cr"])
    result = solve_ahp(
        matrix, names, max_cr=max_cr,
        random_index=config["ahp"]["consistency"]["random_index"],
        raise_on_inconsistent=False,
    )
    return RespondentResult(
        name=name or path.stem,
        matrix=matrix,
        result=result,
        consistency_ratio=result.consistency_ratio,
        accepted=result.consistency_ratio <= max_cr,
        note="" if result.consistency_ratio <= max_cr else f"CR {result.consistency_ratio:.3f} > {max_cr}",
    )


def _data_rows(fh):
    """Yorum satırlarını ve boş satırları atlayıp başlıktan itibaren verir."""
    started = False
    for line in fh:
        stripped = line.strip()
        if not started:
            if stripped.startswith("no,"):
                started = True
                yield line
            continue
        if stripped and not stripped.startswith("#"):
            yield line


def _to_saaty(raw: str, filename: str, a: str, b: str) -> float:
    try:
        value = float(raw.replace(",", "."))
    except ValueError as exc:
        raise ValueError(f"{filename}: '{a}' vs '{b}' cevabı sayı değil: '{raw}'") from exc

    if value == 0 or abs(value) < 1 or abs(value) > 9:
        raise ValueError(
            f"{filename}: '{a}' vs '{b}' cevabı {value} — Saaty ölçeği ±1..±9 aralığında olmalı"
        )
    return value if value > 0 else 1.0 / abs(value)


def aggregate(matrices: list[np.ndarray]) -> np.ndarray:
    """Birden çok uzmanın matrisini geometrik ortalamayla birleştirir (AIJ)."""
    if not matrices:
        raise ValueError("Birleştirilecek matris yok")
    stack = np.stack([np.asarray(m, dtype="float64") for m in matrices])
    if np.any(stack <= 0):
        raise ValueError("Matrislerde pozitif olmayan değer var")

    combined = np.exp(np.log(stack).mean(axis=0))
    # Geometrik ortalama karşılıklılığı korur, ama kayan nokta hatasını
    # temizlemek için köşegeni ve simetriyi açıkça sabitle.
    np.fill_diagonal(combined, 1.0)
    return combined


def group_report(
    config: Config,
    respondents: list[RespondentResult],
    *,
    exclude_inconsistent: bool = True,
) -> tuple[AHPResult, str]:
    """Uzman yanıtlarını birleştirir ve okunur bir rapor üretir.

    Args:
        exclude_inconsistent: CR eşiğini aşan uzmanları birleştirmeye katma.
            Saaty'nin önerisi budur — tutarsız bir yargı kümesi grup sonucunu
            bozar. Dışlanan uzmanlar rapora yazılır, sessizce yok sayılmaz.
    """
    if not respondents:
        raise ValueError("Hiç uzman yanıtı yok")

    max_cr = float(config["ahp"]["consistency"]["max_cr"])
    used = [r for r in respondents if r.accepted] if exclude_inconsistent else list(respondents)

    if not used:
        raise ValueError(
            f"Hiçbir uzman CR <= {max_cr} eşiğini geçemedi. Anket soruları veya "
            "ölçek açıklaması gözden geçirilmeli."
        )

    combined = aggregate([r.matrix for r in used])
    result = solve_ahp(
        combined, config.criteria_order, max_cr=max_cr,
        random_index=config["ahp"]["consistency"]["random_index"],
        raise_on_inconsistent=False,
    )

    lines = [
        f"{'Uzman':<24}{'CR':>9}{'Durum':>14}",
        "-" * 47,
    ]
    for r in respondents:
        status = "kabul" if r.accepted else ("DIŞLANDI" if exclude_inconsistent else "tutarsız (dahil)")
        lines.append(f"{r.name:<24}{r.consistency_ratio:>9.4f}{status:>14}")
    lines.append("-" * 47)
    lines.append(f"Birleştirmeye giren: {len(used)}/{len(respondents)} uzman (geometrik ortalama)")
    lines.append("")
    lines.append(result.summary())
    lines.append("")

    if result.consistency_ratio > max_cr:
        lines.append(
            f"UYARI: birleşik matrisin CR'si {result.consistency_ratio:.4f} > {max_cr}. "
            "Uzmanlar birbirinden belirgin şekilde ayrışıyor; grup içi tartışma "
            "turu (Delphi) önerilir."
        )
    else:
        lines.append(f"Birleşik matris tutarlı (CR = {result.consistency_ratio:.4f} <= {max_cr}).")

    # config.yaml'a yapıştırılabilir biçimde matrisi de ver.
    lines.append("")
    lines.append("config.yaml -> ahp.matrix için (uzman anketi sonucu):")
    for i, row in enumerate(combined):
        cells = ", ".join(f"{v:.4f}" for v in row)
        lines.append(f"    - [{cells}]    # {config.criteria_order[i]}")

    return result, "\n".join(lines)
