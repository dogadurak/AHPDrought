"""Vitrinde hiçbir bulgunun kaybolmadığını sınar.

NEDEN VAR: `web-app/` arayüzü zaman zaman yeniden düzenleniyor — bölümler
katlanır panellere giriyor, listeler metrik kartlara dönüşüyor. Bu tür bir
düzenlemede en kolay yapılan hata, "sadeleştirdim" diyerek bir sayıyı ya da
bir sınırlılığı sessizce düşürmektir. Bileşen saymak bunu yakalamaz (callout
accordion'a dönünce callout sayısı zaten değişir); yakalayan tek şey METNİN
kendisini aramaktır.

NE SINAR: aşağıdaki her parça hem kaynakta hem DERLENMİŞ pakette bulunmalı.
Derlenmiş pakete de bakılır, çünkü asıl soru "kod yazıldı mı" değil,
"yayınlanan sayfada duruyor mu".

Katlanır panelin İÇİNDEKİ metin de bu sınamayı geçer ve geçmelidir: katlamak
gizlemek değildir — içerik DOM'da durur, Ctrl+F bulur, yazdırmada açılır.

    python -m scripts.check_web_content

Çıkış kodu 0: hepsi yerinde. 1: en az bir parça kayıp.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB = PROJECT_ROOT / "web-app"
SUMMARY = WEB / "public" / "data" / "summary.json"

# Arayüz kodunda ELLE yazılı olan bulgular. Bunlar raporlardan alıntıdır;
# summary.json'dan gelmezler, o yüzden bir düzenlemede sessizce düşebilirler.
# Değerler ya düz metin ya da "şu yazımlardan biri yeterli" demek için demet.
REQUIRED_TEXT: dict[str, list[str | tuple[str, ...]]] = {
    "Risk haritası": [
        "0,395",  # sulamalı sürümde tarımın ortalama riski
        "0,439",  # meranın ortalama riski
        "563–860",  # risk zirvesinin kaydığı yamaç eteği kuşağı
    ],
    "Duyarlılık analizi": [
        "%93,1",  # en kötü senaryoda aynı sınıfta kalan piksel
        "%99,3",  # en iyi senaryo
        "0,997",  # Spearman sıra korelasyonu alt sınırı
    ],
    "Doğrulama metrikleri": [
        "%99,7",  # k-means uyumu
        "%79,4",  # senaryo dayanıklılığı
        "−0,283",  # ET/PET ile monoton sıralama
    ],
    "AHP ağırlıkları": [
        "%5,2",  # suya uzaklık nominal ağırlık
        "%2,6",  # efektif katkı — ahp_steep_riskier.md bölüm 2
        "728",  # akarsu ağı uzunluğu (km)
        "0–0,74",  # skorların sıkıştığı bant
    ],
    "Sulama ve NDVI": [
        "2–10",  # yağmura bağlı tarımın kat cinsinden NDVI kaybı
        "2023",  # farkın kaybolduğu yağışlı yıl
    ],
    "Doğrulama / negatif sonuç": [
        "−0,023",  # Landsat kurak yıl ρ — İŞARET KRİTİK, eksi düşerse anlam ters döner
        "+0,045",  # ET/PET ile ikinci bağımsız ölçü
        "+0,013",  # reddedilen hipotezin sonucu
        "0,13",  # Random Forest R²
        "27 yıl",
        "1985–2011",
    ],
    "Dört çıkarım": [
        "İç tutarlılık, geçerlilik değildir",
        "Sonuç ölçü seçimine bağlı değil",
        "Sonuç kriter seçimine de bağlı değil",
        "uydu arşivinin kapsadığı dönemle sınırlıdır",
        "parsel düzeyi yönetim kararlarıdır",  # kapanış paragrafı
    ],
    "Bilinen sınırlılıklar": [
        "Sulama katmanı bir vekildir",
        "Matris uzman anketiyle kurulmadı",
        "Saha verisiyle doğrulama yok",
        "Ölçek uyumsuzluğu",
        "NDVI kısmen döngüsel",
    ],
    "Düzeltilen veri hataları": [
        "04.00",  # Sentinel-2 baseline offset
        "32636",  # yanlış UTM zone
        "32635",  # doğrusu
        "Terra",
        "Aqua",
        "Jenks",
        "%68,9",  # sulama kriterinin sabit tavana yapıştığı alan payı
        "Overpass",
        "PROJ",
    ],
    "İklim serisi": [
        "68 yıl",
        "TerraClimate 1958–2025",
    ],
    # Küçültücü tırnak tipini değiştirir (paket ters tırnak kullanıyor);
    # üç yazımı da kabul ediyoruz.
    "Bölüm çapaları": [
        ('"harita"', "'harita'", "`harita`"),
        ('"agirliklar"', "'agirliklar'", "`agirliklar`"),
        ('"sulama"', "'sulama'", "`sulama`"),
        ('"dogrulama"', "'dogrulama'", "`dogrulama`"),
        ('"yontem"', "'yontem'", "`yontem`"),
    ],
}

# summary.json'dan gelen ve arayüzün mutlaka okuması gereken alanlar.
REQUIRED_DATA_PATHS = [
    "ahp.n_criteria",
    "ahp.consistency_ratio",
    "ahp.cr_threshold",
    "ahp.criteria",
    "classification.classes",
    "classification.total_area_km2",
    "irrigation_effect",
    "operational_years",
    "map_overlay.url",
]


def _dig(data, dotted: str):
    node = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _bundle() -> Path | None:
    """Derlenmiş JS paketi; `npm run build` çalışmamışsa None."""
    hits = sorted((WEB / "dist" / "assets").glob("index-*.js"))
    return hits[-1] if hits else None


def main() -> int:
    source = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((WEB / "src").rglob("*.jsx"))
    )

    bundle_path = _bundle()
    bundle = bundle_path.read_text(encoding="utf-8", errors="replace") if bundle_path else None

    missing: list[str] = []
    checked = 0

    for group, needles in REQUIRED_TEXT.items():
        for needle in needles:
            checked += 1
            forms = needle if isinstance(needle, tuple) else (needle,)
            in_src = any(f in source for f in forms)
            in_bundle = bundle is None or any(f in bundle for f in forms)
            if not in_src:
                missing.append(f"{group}: {forms[0]!r} — KAYNAKTA YOK")
            elif not in_bundle:
                missing.append(f"{group}: {forms[0]!r} — kaynakta var, PAKETTE YOK")

    # Veri sözleşmesi: arayüzün okuduğu alanlar özet dosyasında duruyor mu.
    if SUMMARY.exists():
        data = json.loads(SUMMARY.read_text(encoding="utf-8"))
        for path in REQUIRED_DATA_PATHS:
            checked += 1
            if _dig(data, path) is None:
                missing.append(f"summary.json: {path} alanı yok")
        n = len(data.get("ahp", {}).get("criteria", []))
        checked += 1
        if n != data.get("ahp", {}).get("n_criteria"):
            missing.append(f"summary.json: kriter listesi {n}, n_criteria farklı")
    else:
        missing.append(f"{SUMMARY} yok — önce `python -m scripts.export_web_data`")

    print(f"{checked} parça sınandı.")
    if bundle_path is None:
        print("UYARI: dist/ yok, yalnızca kaynak sınandı (`npm run build` çalıştırın).")
    else:
        print(f"Paket: {bundle_path.relative_to(PROJECT_ROOT)}")

    if missing:
        print(f"\n{len(missing)} parça KAYIP:")
        for m in missing:
            print(f"  - {m}")
        return 1

    print("Hiçbir bulgu kaybolmamış.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
