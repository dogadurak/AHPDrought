"""Ozet sayfasini PDF'e basar.

Artifact HTML'i <!doctype>/<html>/<head>/<body> ICERMEZ — bunlar yayimlama
aninda ekleniyor. Yerel olarak basmak icin ayni iskeleti burada kurmak gerek,
yoksa tarayici quirks moduna duser ve yerlesim kayar.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "reports" / "gediz_ozet.html"   # build_ozet_sayfasi.py uretir
WRAPPED = ROOT / "outputs" / "reports" / "_gediz_ozet_print.html"
OUT = ROOT / "outputs" / "reports" / "gediz_ozet.pdf"

body = SRC.read_text(encoding="utf-8")
title = "Gediz Kuraklık Doğrulaması"

WRAPPED.write_text(
    "<!doctype html>\n"
    '<html lang="tr"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    f"<title>{title}</title>"
    "<style>*{box-sizing:border-box}body{margin:0}</style>"
    f"</head><body>\n{body}\n</body></html>",
    encoding="utf-8",
)

OUT.parent.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 1600})
    page.emulate_media(media="print", color_scheme="light")
    page.goto(WRAPPED.as_uri(), wait_until="load")

    # Gomulu data: URI'ler senkron cozulur ama yine de dekode edilmelerini bekle
    page.wait_for_function(
        "Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)",
        timeout=60000,
    )
    count = page.evaluate("document.images.length")
    broken = page.evaluate(
        "Array.from(document.images).filter(i => !i.naturalWidth)"
        ".map(i => i.alt || '(alt yok)')"
    )
    print(f"  gorsel: {count} yuklendi, bozuk: {broken or 'yok'}")

    page.pdf(
        path=str(OUT),
        format="A4",
        print_background=True,
        margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
        prefer_css_page_size=True,
    )
    browser.close()

size = OUT.stat().st_size
print(f"  PDF: {OUT}  ({size/1e6:.2f} MB)")
if size < 100_000:
    sys.exit("PDF supheli derecede kucuk — icerik basilmamis olabilir")
