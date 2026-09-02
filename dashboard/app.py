"""Streamlit analist paneli — AHP tabanlı tarımsal kuraklık riski, Gediz Havzası.

Bu panel ile React vitrini (`web-app/`) AYNI veri dosyasını okur:
`web-app/public/data/summary.json`, üreteni `scripts/export_web_data.py`.
Hiçbir sayı burada elle yazılmaz; iki arayüz bu yüzden birbirinden sapamaz.

Çalıştırma:
    python -m scripts.export_web_data     # özet + harita kaplaması üret
    streamlit run dashboard/app.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
FIGURES_DIR = BASE_DIR / "outputs" / "figures"
REPORTS_DIR = BASE_DIR / "outputs" / "reports"
WEB_DATA_DIR = BASE_DIR / "web-app" / "public" / "data"
SUMMARY_PATH = WEB_DATA_DIR / "summary.json"

st.set_page_config(
    page_title="Gediz Havzası — Tarımsal Kuraklık Riski",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False)
def load_summary(mtime: float) -> dict:
    """`mtime` yalnızca önbelleği geçersizleştirmek için parametre."""
    del mtime
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def tr_num(value: float, digits: int = 1) -> str:
    """Türkçe biçim: binlik nokta, ondalık virgül. 4634.9 -> "4.634,9"."""
    whole, _, frac = f"{value:,.{digits}f}".partition(".")
    whole = whole.replace(",", ".")
    return f"{whole},{frac}" if frac else whole


def tr_km2(value: float) -> str:
    return f"{tr_num(value)} km²"


def tr_pct(value: float, digits: int = 1) -> str:
    return f"%{tr_num(value, digits)}"


def show_figure(name: str, caption: str | None = None) -> bool:
    """Figürü varsa gösterir; yoksa hangi adımın üreteceğini söyler."""
    path = FIGURES_DIR / name
    if not path.exists():
        st.info(f"`outputs/figures/{name}` henüz üretilmemiş.")
        return False
    st.image(str(path), width="stretch", caption=caption)
    return True


if not SUMMARY_PATH.exists():
    st.error("Özet verisi bulunamadı.")
    st.code("python -m scripts.export_web_data", language="bash")
    st.caption(
        f"Beklenen dosya: {SUMMARY_PATH.relative_to(BASE_DIR)} — "
        "config.yaml ve outputs/reports/ içeriğinden üretilir."
    )
    st.stop()

D = load_summary(SUMMARY_PATH.stat().st_mtime)
CLS = D["classification"]
AHP = D["ahp"]

# --- Yan menü ---------------------------------------------------------------

st.sidebar.title("AHP Kuraklık Riski")
st.sidebar.caption(D["project"]["aoi_name"])

page = st.sidebar.radio(
    "Bölüm",
    [
        "Genel bakış",
        "Kriterler ve ağırlıklar",
        "Zaman serisi",
        "Doğrulama ve sınırlılıklar",
    ],
)

st.sidebar.divider()
st.sidebar.markdown(
    "\n\n".join(
        [
            f"**Senaryo** · `{D['scenario']}`",
            f"**Grid** · {D['grid']['resolution_m']:.0f} m · {D['grid']['crs']}",
            f"**Sürüm** · {D['project']['version']}",
            f"**Veri özeti** · {D['generated']}",
        ]
    )
)
st.sidebar.caption(
    "Bütün sayılar scripts/export_web_data.py çıktısından okunur; "
    "panelde elle yazılmış değer yoktur."
)

# --- Genel bakış ------------------------------------------------------------

if page == "Genel bakış":
    st.title("Genel bakış ve risk haritası")
    st.markdown(
        "Analitik Hiyerarşi Süreci ile kurulan çok kriterli tarımsal kuraklık "
        "modeli. Model yalnızca bitki örtüsünü değil; yağış, toprak su "
        "kapasitesi, yüzey sıcaklığı ve sulama şebekesine uzaklığı da "
        "birleştirir."
    )

    very_high = CLS["classes"][-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sınıflandırılan alan", tr_km2(CLS["total_area_km2"]))
    c2.metric(
        "AHP kriteri",
        str(AHP["n_criteria"]),
        f"CR = {AHP['consistency_ratio']:.4f}",
        delta_color="off",
    )
    c3.metric(
        f"{very_high['label']} risk",
        tr_pct(very_high["share_pct"]),
        tr_km2(very_high["area_km2"]),
        delta_color="off",
    )
    if CLS.get("masked"):
        c4.metric("Maskeli alan", tr_km2(CLS["masked"]["area_km2"]))

    view = st.radio(
        "Harita görünümü",
        ["Etkileşimli", "Statik figür"],
        horizontal=True,
        help="Etkileşimli görünüm export_web_data.py'nin ürettiği kaplamayı kullanır.",
    )

    overlay = D.get("map_overlay")
    if view == "Etkileşimli" and overlay:
        import folium
        from streamlit_folium import st_folium

        png = WEB_DATA_DIR / Path(overlay["url"]).name
        (south, west), (north, east) = overlay["bounds"]

        # Kaplama EPSG:4326'ya yeniden projekte edilmiş halde geliyor;
        # sınırlar da aynı dönüşümden. Raster'ın kendi UTM sınırlarını
        # doğrudan folium'a vermek haritayı dünyanın başka yerine düşürür.
        fmap = folium.Map(
            location=[(south + north) / 2, (west + east) / 2],
            zoom_start=10,
            tiles="CartoDB positron",
        )
        folium.raster_layers.ImageOverlay(
            image=str(png),
            bounds=[[south, west], [north, east]],
            opacity=0.75,
            name="Risk sınıfı",
        ).add_to(fmap)
        folium.LayerControl(collapsed=False).add_to(fmap)
        fmap.fit_bounds([[south, west], [north, east]])
        # st_folium kendi imzasına sahip: `width` bir tamsayı, Streamlit'in
        # "stretch" değerini kabul etmez. Genişletme ayrı bayrakla yapılır.
        st_folium(fmap, use_container_width=True, height=560, returned_objects=[])

        # Lejant: renkler config.yaml'daki ordinal paletten, JSON üzerinden.
        swatches = "".join(
            "<div style='display:flex;align-items:center;gap:8px;font-size:13px'>"
            f"<span style='width:14px;height:14px;border-radius:3px;"
            f"background:{c['color']};display:inline-block'></span>"
            f"<span>{c['label']}</span>"
            f"<span style='margin-left:auto;font-variant-numeric:tabular-nums'>"
            f"{tr_pct(c['share_pct'])}</span></div>"
            for c in CLS["classes"]
        )
        st.markdown(
            "<div style='display:flex;flex-direction:column;gap:4px;max-width:320px'>"
            f"{swatches}</div>",
            unsafe_allow_html=True,
        )
    else:
        if view == "Etkileşimli":
            st.warning(
                "Etkileşimli kaplama üretilmemiş (risk raster'ı yerelde yok). "
                "Statik figür gösteriliyor."
            )
        show_figure(
            f"risk_map_{D['scenario']}.png",
            "5 sınıflı kuraklık risk haritası",
        )

    st.subheader("Risk sınıfı dağılımı")
    dist = pd.DataFrame(CLS["classes"])[
        ["label", "upper_bound", "pixels", "area_km2", "share_pct"]
    ].rename(
        columns={
            "label": "Sınıf",
            "upper_bound": "Üst sınır",
            "pixels": "Piksel",
            "area_km2": "Alan (km²)",
            "share_pct": "Pay (%)",
        }
    )
    st.dataframe(
        dist,
        hide_index=True,
        width="stretch",
        column_config={
            "Pay (%)": st.column_config.ProgressColumn(
                "Pay (%)", format="%.1f%%", min_value=0, max_value=100
            )
        },
    )

    src = CLS.get("source_raster")
    if src:
        note = f"Paylar `{src}` dosyasından sayıldı."
        if CLS.get("report_is_stale"):
            note += (
                f" Sınıf sınırları boş: `outputs/reports/ahp_{D['scenario']}.md` "
                "bu raster'dan eski."
            )
        st.caption(note)

# --- Kriterler --------------------------------------------------------------

elif page == "Kriterler ve ağırlıklar":
    st.title("Model kriterleri ve ağırlıklar")
    st.markdown(
        f"Ağırlıklar {AHP['n_criteria']}×{AHP['n_criteria']} ikili karşılaştırma "
        f"matrisinden özvektör yöntemiyle türetildi. "
        f"λmax = {AHP['lambda_max']:.4f}, CI = {AHP['consistency_index']:.4f}, "
        f"**CR = {AHP['consistency_ratio']:.4f}** (eşik {AHP['cr_threshold']:.2f})."
    )

    crit = pd.DataFrame(
        [
            {
                "Kriter": c["label"],
                "Anahtar": c["key"],
                "Ağırlık (%)": round(c["weight"] * 100, 1),
                "Efektif katkı (%)": c["effective_pct"],
                "Sağlayıcı": (c.get("source") or {}).get("provider") or "—",
                "Koleksiyon": (c.get("source") or {}).get("collection") or "—",
            }
            for c in AHP["criteria"]
        ]
    )

    st.subheader("Nominal ağırlık ve efektif katkı")
    st.bar_chart(
        crit.set_index("Kriter")[["Ağırlık (%)", "Efektif katkı (%)"]],
        horizontal=True,
        height=380,
    )
    st.caption(
        "Efektif katkı = ağırlıkla çarpılmış değerlerin standart sapma payı. "
        "Nominal ağırlığının belirgin altında kalan bir kriter, havzada "
        "ölçeğinin tamamını kullanmıyor demektir."
    )

    st.dataframe(crit, hide_index=True, width="stretch")

    gap = crit.assign(fark=crit["Ağırlık (%)"] - crit["Efektif katkı (%)"]).nlargest(
        1, "fark"
    )
    if not gap.empty and gap.iloc[0]["fark"] > 1.5:
        row = gap.iloc[0]
        st.info(
            f"**{row['Kriter']}** nominal %{row['Ağırlık (%)']:.1f} ağırlığa sahip "
            f"ama efektif katkısı %{row['Efektif katkı (%)']:.1f}. "
            "Kriterin ölçeği var, havzadaki değişkenliği yok."
        )

    st.subheader("Kriter katmanları")
    show_figure(
        f"criteria_panel_{D['scenario']}.png",
        "Normalize edilmiş kriter katmanları (0–1)",
    )

# --- Zaman serisi -----------------------------------------------------------

elif page == "Zaman serisi":
    st.title("Zaman serisi analizleri")

    st.subheader("68 yıllık iklim geçmişi (SPI)")
    show_figure("spi_series.png", "1958–2025 Standartlaştırılmış Yağış İndeksi")
    st.markdown(
        "SPI (McKee ve ark. 1993) TerraClimate yağış serisinden hesaplanıyor. "
        "Doğrulama: ortalama −0,000, standart sapma 1,000. Bağımsız "
        "formülasyonlu PDSI ile r = 0,782."
    )

    st.divider()
    st.subheader("Parsel bazlı mevsimsel değişim (NDVI)")
    col1, col2 = st.columns(2)
    with col1:
        show_figure("ndvi_animation_2024.gif", "Aylık bitki örtüsü değişimi (2024)")
    with col2:
        show_figure("ndvi_parcel_curves_2024.png", "Arazi örtüsüne göre NDVI eğrileri")
        st.markdown(
            "**Bulgu:** tarım alanları temmuzda zirve yapıyor — havzanın en "
            "kurak dönemi. Bu, yağışa değil **sulamaya** dayalı bir tarım "
            "demek. Mera tam tersi: nisanda zirve, ağustosta dip."
        )

    if D.get("operational_years"):
        st.divider()
        st.subheader("Yıl bazında kuraklık şiddeti ve gözlenen etki")
        ops = pd.DataFrame(D["operational_years"])
        st.bar_chart(ops.set_index("year")[["spi"]], height=240)
        st.caption("SPI-12: negatif değerler kurak yılları gösterir.")
        st.dataframe(
            ops.rename(
                columns={
                    "year": "Yıl",
                    "spi": "SPI",
                    "dry": "Kurak",
                    "mean_anomaly": "Ort. anomali",
                    "risk_anomaly_rho": "risk–anomali ρ",
                    "monotonic": "Monoton",
                }
            ),
            hide_index=True,
            width="stretch",
        )

# --- Doğrulama --------------------------------------------------------------

else:
    st.title("Doğrulama ve sınırlılıklar")
    st.markdown(
        "Bu projenin ayırt edici yönü, AHP sonuçlarını bağımsız uydu ve iklim "
        "verisiyle sınamış ve **olumsuz sonucu raporlamış** olması."
    )

    if D.get("irrigation_effect"):
        st.subheader("Sulama, NDVI'daki kuraklık sinyalini maskeliyor")
        irr = pd.DataFrame(D["irrigation_effect"]).sort_values("year")
        chart_df = irr.set_index("year")[["near_canal", "far_from_canal"]].rename(
            columns={
                "near_canal": "Kanala < 2 km",
                "far_from_canal": "Kanaldan > 10 km",
            }
        )
        st.bar_chart(chart_df, height=300)

        st.dataframe(
            irr.rename(
                columns={
                    "year": "Yıl",
                    "condition": "Durum",
                    "near_canal": "Kanala < 2 km",
                    "far_from_canal": "Kanaldan > 10 km",
                }
            )[["Yıl", "Durum", "Kanala < 2 km", "Kanaldan > 10 km"]],
            hide_index=True,
            width="stretch",
        )
        st.success(
            "Yağmura bağlı tarım, kurak yıllarda sulanan tarımdan 3–10 kat "
            "fazla NDVI kaybediyor. Yağışlı yılda iki grup arasında fark yok — "
            "fark yalnızca stres varken ortaya çıkıyor."
        )
        st.warning(
            "Metodolojik sonuç: **sulanan bir havzada NDVI, tarımsal kuraklık "
            "etkisini ölçemez.** Çiftçi sularsa yeşillik korunur; etki suya, "
            "maliyete ve rezervuar seviyesine yansır, spektruma değil."
        )
        show_figure("summary_irrigation.png")

    st.divider()
    st.subheader("Mekânsal kuraklık izleme")
    show_figure("ndvi_anomaly_2024.png", "2024 NDVI anomalisi (leave-one-out z-skoru)")

    st.divider()
    st.subheader("Geçemediği sınama")
    st.error(
        "**AHP risk haritası, kuraklıkta bitki örtüsünün nerede zarar "
        "göreceğini öngörmüyor.** Landsat 5 ile 27 yıl / 7 gerçek kurak yıl "
        "(1985–2011) sınandı: kurak yıl ortalama ρ = −0,021 — sıralama yok. "
        "İkinci ve bağımsız bir etki ölçüsü (ET/PET) aynı sonucu verdi "
        "(ρ = +0,050). 'Düşük değişkenlikli kriterler bozuyor' hipotezi "
        "kuruldu ve reddedildi."
    )
    st.markdown(
        "Model iç tutarlılık ölçütlerinin hepsini geçiyor — CR, k-means "
        "çapraz kontrolü, ağırlık duyarlılığı. Literatürdeki AHP kuraklık "
        "haritalarının büyük kısmı tam da burada durur. **İç tutarlılık, "
        "geçerlilik değildir.**"
    )

    # Adım 13 raporu etki ölçüsüne göre ayrı dosyalara yazar
    # (historical_test_ndvi.md / historical_test_et.md). Eskiden tek bir
    # historical_test.md vardı; o ad artık üretilmiyor.
    for name in (
        "validation_report.md",
        "ahp_steep_riskier.md",
        "historical_test_ndvi.md",
        "historical_test_et.md",
        "ml_baseline_physical.md",
    ):
        path = REPORTS_DIR / name
        if path.exists():
            with st.expander(f"Tam rapor — {name}"):
                st.markdown(path.read_text(encoding="utf-8"))
