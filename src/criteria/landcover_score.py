"""Arazi örtüsü sınıflarının kuraklık duyarlılık skoruna çevrilmesi (Adım 3).

Skorlar `lookups/worldcover_susceptibility.json` içinde, her biri gerekçesiyle
birlikte tutulur — kodda tek bir sınıf skoru yoktur.

`score: null` olan sınıflar (yerleşim, su yüzeyi, kar/buz, mangrov) MASKELENİR.
Gerekçe: tarımsal kuraklık riski bu yüzeylerde tanımsızdır. Bu, nihai risk
haritasında bilinçli boşluklar bırakır; sıfır risk atamak bu pikselleri "güvenli
tarım alanı" gibi gösterirdi ve yanıltıcı olurdu.
"""

from __future__ import annotations

import numpy as np

from ..config import Config, load_json


def landcover_susceptibility(codes: np.ndarray, config: Config) -> np.ndarray:
    """Sınıf kodu raster'ını 0-1 duyarlılık skoruna çevirir (maskeliler NaN)."""
    lookup = load_json(config["data_sources"]["landcover"]["lookup_file"])["classes"]

    present = set(np.unique(codes).tolist()) - {0}
    unknown = sorted(code for code in present if str(code) not in lookup)
    if unknown:
        raise ValueError(
            f"Lookup tablosunda karşılığı olmayan arazi örtüsü sınıfları: {unknown}. "
            f"{config['data_sources']['landcover']['lookup_file']} güncellenmeli."
        )

    scores = np.full(codes.shape, np.nan, dtype="float32")
    masked_codes = []

    for code_str, entry in lookup.items():
        code = int(code_str)
        if code not in present:
            continue
        score = entry.get("score")
        if score is None:
            masked_codes.append(f"{code} ({entry.get('name', '?')})")
            continue  # NaN kalır
        if not 0.0 <= float(score) <= 1.0:
            raise ValueError(f"Sınıf {code}: skor 0-1 aralığında olmalı, {score} verildi")
        scores[codes == code] = float(score)

    masked_fraction = float(np.isnan(scores).mean())
    if masked_codes:
        print(f"      maskelenen sınıflar: {', '.join(masked_codes)} -> %{100 * masked_fraction:.2f}")
    if masked_fraction > 0.5:
        raise ValueError(
            f"Alanın %{100 * masked_fraction:.0f}'i maskelendi — lookup tablosunu kontrol edin"
        )

    return scores
