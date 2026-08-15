"""Ozet sayfasini kurar: gorselleri optimize edip base64 ile gomer.

Kodlama secimi ICERIGE gore yapilir:
  JPEG  -> surekli tonlu haritalar. PNG'de neredeyse her piksel farkli renk
           oldugu icin sikismiyor; ilk denemede risk haritasi 519 KB'den
           1494 KB'ye BUYUMUSTU. JPEG'de dortte birine iniyor.
  PNG-8 -> duz renkli grafikler (cubuk, cizgi, metin). Az sayida renk oldugu
           icin palet indirgeme gozle fark edilmeden cok kucultuyor.
"""

import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIG = ROOT / "outputs" / "figures"
TEMPLATE = ROOT / "docs" / "ozet_sablon.html"
# Tek dosyalik sayfa: 4 MB'lik gomulu gorsel iceriyor, repoya girmez
# (.gitignore'da outputs/**/*.html yok ama PDF yeterli cikti).
OUT = ROOT / "outputs" / "reports" / "gediz_ozet.html"

# dosya -> (hedef genislik px, bicim)
PLAN = {
    "summary_forecast_skill.png":       (1400, "png8"),
    "summary_validation.png":           (1400, "png8"),
    "summary_irrigation.png":           (1200, "png8"),
    "spi_series.png":                   (1500, "png8"),
    "ndvi_parcel_curves_2024.png":      (1250, "png8"),
    "seasonal_predictor.png":           (1050, "png8"),
    "risk_map_steep_riskier.png":       (1450, "jpeg"),
    "criteria_panel_steep_riskier.png": (1500, "jpeg"),
    "ndvi_anomaly_2024.png":            (1150, "jpeg"),
}


def encode(name: str, width: int, fmt: str) -> str:
    src = FIG / name
    img = Image.open(src).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)

    buf = io.BytesIO()
    if fmt == "jpeg":
        img.save(buf, format="JPEG", quality=86, optimize=True, progressive=True)
        mime = "image/jpeg"
    else:
        quantized = img.convert("P", palette=Image.ADAPTIVE, colors=128)
        quantized.save(buf, format="PNG", optimize=True)
        mime = "image/png"

    data = buf.getvalue()
    print(f"  {name:<42}{src.stat().st_size/1024:8.0f} ->{len(data)/1024:8.0f} KB   {fmt}")
    return f"data:{mime};base64," + base64.b64encode(data).decode()


print("Gorseller:")
IMG = {name: encode(name, w, f) for name, (w, f) in PLAN.items()}

gif = (FIG / "ndvi_animation_2024.gif").read_bytes()
IMG["ndvi_animation_2024.gif"] = "data:image/gif;base64," + base64.b64encode(gif).decode()
print(f"  {'ndvi_animation_2024.gif':<42}{len(gif)/1024:8.0f} KB (oldugu gibi)")

print(f"\nToplam gomulu: {sum(len(v) for v in IMG.values())/1e6:.2f} MB (base64)")

template = TEMPLATE.read_text(encoding="utf-8")
for key, uri in IMG.items():
    template = template.replace("{{" + key + "}}", uri)

leftover = [line for line in template.splitlines() if "{{" in line]
assert not leftover, f"sablonda doldurulmamis yer var: {leftover[:2]}"

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(template, encoding="utf-8")
print(f"Yazildi: {OUT.name}  ({OUT.stat().st_size/1e6:.2f} MB)")
