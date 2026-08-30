import streamlit as st
import os

st.set_page_config(
    page_title="Tarımsal Kuraklık Risk Haritası",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Proje dizinleri (dashboard klasörünün bir üstü)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGURES_DIR = os.path.join(BASE_DIR, "outputs", "figures")
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

# Özel stil
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #2E86C1;
        font-weight: 700;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #7F8C8D;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# Yan Menü (Sidebar)
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/T.C._Tar%C4%B1m_ve_Orman_Bakanl%C4%B1%C4%9F%C4%B1_Logo.svg/1200px-T.C._Tar%C4%B1m_ve_Orman_Bakanl%C4%B1%C4%9F%C4%B1_Logo.svg.png", width=100) # Sembolik logo
st.sidebar.title("AHP Kuraklık Riski")
st.sidebar.markdown("Gediz Havzası (Manisa - Salihli)")

page = st.sidebar.radio(
    "Menü",
    ["Genel Bakış", "Kriterler ve Etki", "Zaman Serisi (NDVI & SPI)", "Doğrulama ve Analiz"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("**Hazırlayan:** Veri Bilimi Ekibi")
st.sidebar.markdown("**Veri Yılı:** 2017 - 2025")

if page == "Genel Bakış":
    st.markdown('<p class="main-header">Genel Bakış ve Risk Haritası</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Gediz Havzası Çok Kriterli Tarımsal Kuraklık Modeli</p>', unsafe_allow_html=True)
    
    st.markdown("""
    Bu proje, **Analitik Hiyerarşi Süreci (AHP)** kullanılarak Gediz Havzası için 9 kriterli bir tarımsal kuraklık risk modeli oluşturmuştur.
    Model, sadece bitki örtüsünü değil; yağış, toprak su kapasitesi, yüzey sıcaklığı ve sulama şebekesine uzaklık gibi hidrolojik 
    ve yapısal faktörleri de birleştirir.
    """)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Toplam Alan", "4.842 km²")
    col2.metric("En Riskli Alan (Çok Yüksek)", "% 11.0", "-508 km²")
    col3.metric("Sulama Katkısı", "Yüksek", "+ Tarımı koruyor")
    
    map_type = st.radio("Harita Görünümü", ["Statik Görsel (Hızlı)", "Etkileşimli Harita (Detaylı)"], horizontal=True)
    
    if map_type == "Statik Görsel (Hızlı)":
        risk_map_path = os.path.join(FIGURES_DIR, "risk_map_steep_riskier.png")
        if os.path.exists(risk_map_path):
            st.image(risk_map_path, use_container_width=True, caption="5 Sınıflı Kuraklık Risk Haritası")
        else:
            st.warning("Risk haritası bulunamadı. Lütfen analizleri çalıştırın.")
    else:
        import folium
        from streamlit_folium import st_folium
        import rasterio
        import numpy as np
        
        tif_path = os.path.join(DATA_DIR, "risk_class_steep_riskier.tif")
        if os.path.exists(tif_path):
            with st.spinner("Harita yükleniyor..."):
                with rasterio.open(tif_path) as src:
                    bounds = src.bounds
                    data = src.read(1)
                    nodata = src.nodata
                
                # 5 Sınıf için renk paleti (RGB formatında, 0-255 arası)
                # Sınıflar: 1: Çok düşük, 2: Düşük, 3: Orta, 4: Yüksek, 5: Çok Yüksek
                colors = {
                    1: [44, 123, 182],   # Mavi
                    2: [171, 217, 233],  # Açık mavi
                    3: [255, 255, 191],  # Sarı
                    4: [253, 174, 97],   # Turuncu
                    5: [215, 25, 28]     # Kırmızı
                }
                
                # RGBA resmi oluştur
                h, w = data.shape
                rgba = np.zeros((h, w, 4), dtype=np.uint8)
                
                for val, color in colors.items():
                    mask = data == val
                    rgba[mask, :3] = color
                    rgba[mask, 3] = 180  # Şeffaflık (Alpha)
                
                # Nodata piksellerini tam şeffaf yap
                if nodata is not None:
                    rgba[data == nodata, 3] = 0
                
                min_lon, min_lat, max_lon, max_lat = bounds.left, bounds.bottom, bounds.right, bounds.top
                center_lat = (min_lat + max_lat) / 2
                center_lon = (min_lon + max_lon) / 2
                
                m = folium.Map(location=[center_lat, center_lon], zoom_start=9, tiles="CartoDB positron")
                
                folium.raster_layers.ImageOverlay(
                    image=rgba,
                    bounds=[[min_lat, min_lon], [max_lat, max_lon]],
                    opacity=0.7,
                    name="Risk Haritası"
                ).add_to(m)
                
                st_folium(m, width=900, height=600, returned_objects=[])
        else:
            st.warning("TIFF dosyası bulunamadı. Lütfen analizleri çalıştırın.")

elif page == "Kriterler ve Etki":
    st.markdown('<p class="main-header">Model Kriterleri ve Ağırlıklar</p>', unsafe_allow_html=True)
    
    st.markdown("""
    Model 9 farklı kriterden oluşmaktadır. Ağırlıklar özvektör (eigenvector) yöntemiyle hesaplanmış olup 
    tutarlılık oranı **CR = 0.0093** (eşik 0.10) olarak bulunmuştur.
    """)
    
    criteria_path = os.path.join(FIGURES_DIR, "criteria_panel_steep_riskier.png")
    if os.path.exists(criteria_path):
        st.image(criteria_path, use_container_width=True, caption="Kriter Katmanları (Normalize Edilmiş)")

elif page == "Zaman Serisi (NDVI & SPI)":
    st.markdown('<p class="main-header">Zaman Serisi Analizleri</p>', unsafe_allow_html=True)
    
    st.subheader("68 Yıllık İklim Geçmişi (SPI)")
    spi_path = os.path.join(FIGURES_DIR, "spi_series.png")
    if os.path.exists(spi_path):
        st.image(spi_path, use_container_width=True, caption="1958-2025 Standartlaştırılmış Yağış İndeksi (SPI)")
        
    st.markdown("---")
    
    st.subheader("Parsel Bazlı Mevsimsel Değişim (NDVI)")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        ndvi_anim = os.path.join(FIGURES_DIR, "ndvi_animation_2024.gif")
        if os.path.exists(ndvi_anim):
            st.image(ndvi_anim, caption="Aylık Bitki Örtüsü Değişimi (2024)")
            
    with col2:
        ndvi_curve = os.path.join(FIGURES_DIR, "ndvi_parcel_curves_2024.png")
        if os.path.exists(ndvi_curve):
            st.image(ndvi_curve, caption="Arazi Örtüsüne Göre Ortalama NDVI Eğrileri")
            st.markdown("""
            **Önemli Bulgu:** Tarım alanları (mavi) yazın ortasında en yüksek yeşilliğe (NDVI) ulaşıyor. 
            Oysa bu dönem havzanın en kurak dönemi. Bu durum, bitkilerin yağışa değil **sulamaya (Demirköprü Barajı)** bağımlı olduğunu kanıtlar.
            """)

elif page == "Doğrulama ve Analiz":
    st.markdown('<p class="main-header">Model Doğrulaması (Validation)</p>', unsafe_allow_html=True)
    
    st.markdown("""
    Bu projenin en güçlü yönü, AHP sonuçlarını bağımsız uydu ve iklim verileriyle (ET/PET ve geçmiş Landsat uydu görüntüleri) acımasızca sınamış olmasıdır.
    """)
    
    st.subheader("Sulama Şebekesinin Koruyucu Etkisi")
    irr_path = os.path.join(FIGURES_DIR, "summary_irrigation.png")
    
    if os.path.exists(irr_path):
        st.image(irr_path, use_container_width=True)
    else:
        st.info("Kurak yıllarda tarım alanı NDVI anomalisi, sulama şebekesine uzaklaştıkça **10 kat daha fazla** düşmektedir. Model bunu başarıyla yakaladı.")

    st.subheader("Kuraklık İzleme: NDVI Anomalisi")
    anomaly_path = os.path.join(FIGURES_DIR, "ndvi_anomaly_2024.png")
    if os.path.exists(anomaly_path):
        st.image(anomaly_path, use_container_width=True, caption="Normalden sapmayı gösteren Z-skoru")
