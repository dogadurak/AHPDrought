"""Grup AHP anket araçlarının testleri.

Anketin kendisi insan işidir; burada test edilen, **cevapların matrise doğru
çevrilmesi ve doğru şekilde birleştirilmesidir** — bu adımda yapılacak bir
hata, uzman görüşünü sessizce çarpıtır.
"""

from __future__ import annotations

import csv
import itertools

import numpy as np
import pytest

from src.ahp import solve_ahp
from src.ahp_survey import (
    aggregate,
    group_report,
    read_response,
    write_questionnaire,
)
from src.config import load_config


@pytest.fixture
def config():
    return load_config()


def fill_form(config, path, matrix) -> None:
    """Verilen matristen doldurulmuş bir anket formu üretir (test yardımcısı)."""
    names = config.criteria_order
    index = {n: i for i, n in enumerate(names)}
    rows = []
    for a, b in itertools.combinations(names, 2):
        value = matrix[index[a], index[b]]
        signed = value if value >= 1 else -round(1 / value)
        rows.append([a, b, f"{signed:g}"])

    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["# test formu"])
        writer.writerow(["no", "A_kod", "A_aciklama", "B_kod", "B_aciklama", "cevap"])
        for i, (a, b, answer) in enumerate(rows, start=1):
            writer.writerow([i, a, "", b, "", answer])


def consistent_matrix(weights) -> np.ndarray:
    w = np.asarray(weights, dtype=float)
    return w[:, None] / w[None, :]


# --- Form üretimi ------------------------------------------------------------


def test_questionnaire_has_one_row_per_pair(config, tmp_path):
    path = write_questionnaire(config, tmp_path / "form.csv")
    n = len(config.criteria_order)

    with path.open("r", encoding="utf-8-sig") as fh:
        data_lines = [ln for ln in fh if ln.strip() and not ln.startswith("#")]

    # 1 başlık satırı + n(n-1)/2 soru
    assert len(data_lines) == 1 + n * (n - 1) // 2


def test_questionnaire_covers_every_pair_exactly_once(config, tmp_path):
    path = write_questionnaire(config, tmp_path / "form.csv")
    pairs = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for line in fh:
            parts = next(csv.reader([line]))
            if len(parts) == 6 and parts[0].isdigit():
                pairs.append((parts[1], parts[3]))

    expected = set(itertools.combinations(config.criteria_order, 2))
    assert set(pairs) == expected
    assert len(pairs) == len(expected), "aynı çift birden fazla soruluyor"


# --- Yanıt okuma -------------------------------------------------------------


def test_response_roundtrip_recovers_the_matrix(config, tmp_path):
    """Formdan okunan matris, formu üreten matrisle aynı olmalı."""
    n = len(config.criteria_order)
    original = np.array(config["ahp"]["matrix"], dtype=float)

    path = tmp_path / "uzman.csv"
    fill_form(config, path, original)
    recovered = read_response(config, path).matrix

    # Form işaretli tamsayı taşır; config'teki 0.3333 gibi değerler tam
    # karşılıklarına yuvarlanır, bu yüzden gevşek tolerans.
    np.testing.assert_allclose(recovered, original, rtol=0.02)


def test_response_matrix_is_reciprocal(config, tmp_path):
    path = tmp_path / "uzman.csv"
    fill_form(config, path, np.array(config["ahp"]["matrix"], dtype=float))
    matrix = read_response(config, path).matrix

    np.testing.assert_allclose(matrix * matrix.T, 1.0, atol=1e-9)
    np.testing.assert_allclose(np.diag(matrix), 1.0)


def test_negative_answer_means_b_is_more_important(config, tmp_path):
    """-5, 'B kriteri A'dan belirgin daha önemli' demektir."""
    names = config.criteria_order
    path = tmp_path / "uzman.csv"

    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["no", "A_kod", "A_aciklama", "B_kod", "B_aciklama", "cevap"])
        for i, (a, b) in enumerate(itertools.combinations(names, 2), start=1):
            writer.writerow([i, a, "", b, "", "-5" if i == 1 else "1"])

    matrix = read_response(config, path).matrix
    assert matrix[0, 1] == pytest.approx(0.2)
    assert matrix[1, 0] == pytest.approx(5.0)


def test_missing_answer_is_rejected(config, tmp_path):
    path = tmp_path / "eksik.csv"
    fill_form(config, path, np.array(config["ahp"]["matrix"], dtype=float))
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    lines[-1] = lines[-1].rsplit(",", 1)[0] + ","  # son cevabı sil
    path.write_text("\n".join(lines), encoding="utf-8-sig")

    with pytest.raises(ValueError, match="cevaplanmamış"):
        read_response(config, path)


@pytest.mark.parametrize("bad", ["0", "12", "-15", "abc", "0.5"])
def test_out_of_scale_answers_are_rejected(config, tmp_path, bad):
    names = config.criteria_order
    path = tmp_path / "hatali.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["no", "A_kod", "A_aciklama", "B_kod", "B_aciklama", "cevap"])
        for i, (a, b) in enumerate(itertools.combinations(names, 2), start=1):
            writer.writerow([i, a, "", b, "", bad if i == 1 else "1"])

    with pytest.raises(ValueError):
        read_response(config, path)


# --- Birleştirme -------------------------------------------------------------


def test_geometric_mean_cancels_opposing_judgements():
    """3 ve 1/3 diyen iki uzmanın ortalaması 1 olmalı — aritmetik ortalama 1.67 verirdi."""
    a = np.array([[1.0, 3.0], [1 / 3, 1.0]])
    b = np.array([[1.0, 1 / 3], [3.0, 1.0]])

    combined = aggregate([a, b])
    np.testing.assert_allclose(combined, np.ones((2, 2)), atol=1e-12)

    arithmetic = (a + b) / 2
    assert arithmetic[0, 1] == pytest.approx(1.6667, abs=1e-3), "karşılaştırma: aritmetik kayırırdı"


def test_aggregation_preserves_reciprocity():
    """Aritmetik ortalamanın koruyamadığı özellik: a_ij * a_ji = 1."""
    rng = np.random.default_rng(0)
    matrices = []
    for _ in range(4):
        w = rng.random(5) + 0.1
        matrices.append(w[:, None] / w[None, :])

    combined = aggregate(matrices)
    np.testing.assert_allclose(combined * combined.T, 1.0, atol=1e-10)


def test_aggregating_identical_matrices_is_a_noop():
    m = consistent_matrix([0.4, 0.3, 0.2, 0.1])
    np.testing.assert_allclose(aggregate([m, m, m]), m, atol=1e-12)


def test_aggregate_rejects_empty_input():
    with pytest.raises(ValueError, match="matris yok"):
        aggregate([])


# --- Grup raporu -------------------------------------------------------------


def _respondents(config, tmp_path, matrices):
    results = []
    for i, m in enumerate(matrices):
        path = tmp_path / f"uzman_{i}.csv"
        fill_form(config, path, m)
        results.append(read_response(config, path, name=f"uzman_{i}"))
    return results


def test_group_report_excludes_inconsistent_respondents(config, tmp_path):
    n = len(config.criteria_order)
    good = consistent_matrix(np.linspace(0.3, 0.05, n))

    # Kasıtlı olarak çelişkili: her çifte rastgele uç değerler
    rng = np.random.default_rng(7)
    bad = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            v = float(rng.choice([9, 7, 1 / 9, 1 / 7]))
            bad[i, j], bad[j, i] = v, 1 / v

    respondents = _respondents(config, tmp_path, [good, good, bad])
    assert respondents[2].accepted is False

    result, report = group_report(config, respondents, exclude_inconsistent=True)
    assert "DIŞLANDI" in report
    assert "2/3 uzman" in report
    assert result.consistency_ratio <= config["ahp"]["consistency"]["max_cr"]


def test_group_report_can_keep_inconsistent_respondents(config, tmp_path):
    n = len(config.criteria_order)
    good = consistent_matrix(np.linspace(0.3, 0.05, n))
    respondents = _respondents(config, tmp_path, [good, good])

    _, report = group_report(config, respondents, exclude_inconsistent=False)
    assert "2/2 uzman" in report


def test_group_report_emits_pasteable_matrix(config, tmp_path):
    """Rapor, config.yaml'a doğrudan yapıştırılabilir bir matris içermeli."""
    n = len(config.criteria_order)
    good = consistent_matrix(np.linspace(0.3, 0.05, n))
    _, report = group_report(config, _respondents(config, tmp_path, [good]))

    assert "ahp.matrix" in report
    matrix_lines = [ln for ln in report.splitlines() if ln.strip().startswith("- [")]
    assert len(matrix_lines) == n
    for name in config.criteria_order:
        assert any(name in ln for ln in matrix_lines)


def test_group_report_needs_at_least_one_usable_response(config, tmp_path):
    n = len(config.criteria_order)
    rng = np.random.default_rng(1)
    bad = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            v = float(rng.choice([9, 1 / 9]))
            bad[i, j], bad[j, i] = v, 1 / v

    respondents = _respondents(config, tmp_path, [bad])
    with pytest.raises(ValueError, match="eşiğini geçemedi"):
        group_report(config, respondents, exclude_inconsistent=True)
