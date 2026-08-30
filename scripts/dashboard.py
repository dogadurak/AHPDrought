"""
GEDIZ DROUGHT INTELLIGENCE
Premium Geospatial Scientific Dashboard
"""

import os
if "PROJ_LIB" in os.environ:
    del os.environ["PROJ_LIB"]

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import rasterio
from rasterio.warp import transform_bounds
import folium
from streamlit_folium import st_folium
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import io
import base64

# ==========================================
# PAGE CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="Gediz Drought Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# CSS INJECTION (BLOOMBERG/ARCGIS STYLE)
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #080B12;
    color: #cbd5e1;
}

[data-testid="stSidebar"] {
    background-color: #0D111A;
    border-right: 1px solid #1e293b;
}

h1, h2, h3, h4, h5, h6 {
    font-family: 'Space Grotesk', sans-serif;
    color: #f8fafc;
    font-weight: 600;
}

.top-header {
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid #1e293b;
}
.top-header h1 {
    font-size: 1.2rem;
    letter-spacing: 0.15em;
    color: #38bdf8;
    margin-bottom: 0.2rem;
    text-transform: uppercase;
}
.top-header p {
    font-size: 0.95rem;
    color: #94a3b8;
    margin: 0;
}

.panel {
    background-color: #111722;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 1.5rem;
    height: 100%;
}

.metric-value {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 3rem;
    font-weight: 700;
    color: #38bdf8;
    line-height: 1;
}
.metric-label {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #64748b;
    margin-top: 0.5rem;
    font-weight: 600;
}

.pipeline-item {
    text-align: center;
    padding: 1rem;
    background: #0D111A;
    border: 1px solid #1e293b;
    border-radius: 8px;
}
.pipeline-num {
    font-family: 'Space Grotesk', sans-serif;
    color: #38bdf8;
    font-size: 1.1rem;
    font-weight: 700;
}
.pipeline-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: #f8fafc;
    margin: 0.5rem 0 0.2rem 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.pipeline-desc {
    font-size: 0.8rem;
    color: #64748b;
}

.section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1rem;
    color: #f8fafc;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid #1e293b;
    padding-bottom: 0.5rem;
}

.data-row {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(30, 41, 59, 0.5);
    font-size: 0.85rem;
}
.data-label { color: #94a3b8; }
.data-val { color: #f8fafc; font-weight: 500; font-family: 'Space Grotesk', monospace; }

hr { border-color: #1e293b; margin: 3rem 0; }

.warning-text { color: #ef4444; }
.safe-text { color: #38bdf8; }

/* Customizing Streamlit Tabs/Radios */
div.stRadio > div { background: transparent; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# UTILS & DATA LOADING
# ==========================================
BASE = Path(".")

@st.cache_data(show_spinner=False)
def load_tiff_metadata_and_downsample(tiff_path: str, downsample: int = 4):
    with rasterio.open(tiff_path) as src:
        data = src.read(1)[::downsample, ::downsample]
        nodata = src.nodata
        bounds_utm = src.bounds
        crs = src.crs
    west, south, east, north = transform_bounds(crs, "EPSG:4326",
                                                 bounds_utm.left, bounds_utm.bottom,
                                                 bounds_utm.right, bounds_utm.top)
    return data, nodata, [[south, west], [north, east]]

def generate_overlay_png(data, nodata, cmap_name, vmin, vmax):
    cmap = plt.get_cmap(cmap_name)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    masked = np.where((data == nodata) | np.isnan(data), np.nan, data)
    rgba = cmap(norm(masked))
    rgba[np.isnan(masked)] = [0, 0, 0, 0]
    img = Image.fromarray((rgba * 255).astype(np.uint8))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

def build_map(tiff_path, cmap, vmin, vmax, layer_name, height=600):
    if not Path(tiff_path).exists():
        m = folium.Map(location=[38.5, 28.0], zoom_start=8, tiles="CartoDB dark_matter")
        return m, height

    data, nodata, bounds = load_tiff_metadata_and_downsample(tiff_path)
    png_buf = generate_overlay_png(data, nodata, cmap, vmin, vmax)
    
    center = [(bounds[0][0] + bounds[1][0]) / 2, (bounds[0][1] + bounds[1][1]) / 2]
    
    m = folium.Map(location=center, zoom_start=9, tiles="CartoDB dark_matter", control_scale=True, zoom_control=False)
    
    encoded = base64.b64encode(png_buf.read()).decode()
    img_url = f"data:image/png;base64,{encoded}"
    
    folium.raster_layers.ImageOverlay(
        image=img_url,
        bounds=bounds,
        opacity=0.85,
        name=layer_name,
        interactive=True,
    ).add_to(m)
    return m, height

# ==========================================
# SIDEBAR
# ==========================================
with st.sidebar:
    st.markdown("""
    <div style="margin-bottom: 2rem;">
        <h2 style="color: #f8fafc; font-size: 1.2rem; margin:0; letter-spacing: 0.05em;">GEDIZ</h2>
        <div style="color: #38bdf8; font-size: 0.85rem; font-family: 'Space Grotesk', sans-serif; font-weight: 600; letter-spacing: 0.1em;">DROUGHT INTELLIGENCE</div>
    </div>
    """, unsafe_allow_html=True)
    
    page = st.radio(
        "",
        ["OVERVIEW", 
         "01 — PHYSICAL RISK", 
         "02 — PHYSICAL BASELINE", 
         "03 — PHYSICAL–OBSERVED MISMATCH", 
         "04 — HISTORICAL DECOUPLING"],
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='margin-top: 4rem;'></div>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style='font-size: 0.75rem; color: #64748b; border-top: 1px solid #1e293b; padding-top: 1rem;'>
    <div style='margin-bottom: 0.8rem;'><b style='color:#94a3b8;'>STUDY AREA</b><br>Gediz Basin, Türkiye</div>
    <div style='margin-bottom: 0.8rem;'><b style='color:#94a3b8;'>PERIOD</b><br>1985–2011</div>
    <div style='margin-bottom: 0.8rem;'><b style='color:#94a3b8;'>OBSERVATION</b><br>Landsat NDVI</div>
    <div style='margin-bottom: 0.8rem;'><b style='color:#94a3b8;'>VALIDATION</b><br>100 × 100 Spatial Blocks</div>
    <div style='margin-bottom: 0.8rem;'><b style='color:#94a3b8;'>MODEL</b><br>Random Forest</div>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# HEADER (All Pages)
# ==============================================================================
st.markdown("""
<div class="top-header">
    <h1>GEDIZ / DROUGHT INTELLIGENCE</h1>
    <p>Physical drought risk, satellite-observed agricultural stress, and their changing spatial relationship.<br>
    <span style="font-size: 0.85rem; color: #64748b;">Gediz Basin · Türkiye | 1985–2011</span></p>
</div>
""", unsafe_allow_html=True)

# ==============================================================================
# PAGE: OVERVIEW
# ==============================================================================
if page == "OVERVIEW":
    
    col_map, col_panel = st.columns([7, 3])
    
    with col_map:
        st.markdown("<div style='border: 1px solid #1e293b; border-radius: 8px; overflow: hidden;'>", unsafe_allow_html=True)
        risk_tif = BASE / "data" / "processed" / "risk_index_steep_riskier.tif"
        fmap, h = build_map(str(risk_tif), "YlOrRd", 0.0, 1.0, "Physical Risk", height=500)
        st_folium(fmap, height=h, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_panel:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='font-family: Space Grotesk; color:#64748b; font-size:0.8rem; letter-spacing:0.1em; margin-bottom:1rem;'>RESEARCH SIGNAL</div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div class="metric-value">0.13</div>
        <div style="font-size:0.85rem; color:#f8fafc; font-weight:600; margin-top:5px; margin-bottom:20px;">R² / LIMITED PHYSICAL EXPLANATORY POWER</div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='border-top: 1px solid #1e293b; margin: 15px 0;'></div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style="font-size:0.85rem; color:#38bdf8; font-weight:600; margin-bottom:10px;">TEMPORAL DECOUPLING</div>
        <div style="margin-bottom:10px;">
            <span style="color:#f8fafc; font-size:0.85rem; font-weight:600;">1980s–90s</span><br>
            <span style="color:#94a3b8; font-size:0.8rem;">stronger spatial alignment</span>
        </div>
        <div>
            <span style="color:#f8fafc; font-size:0.85rem; font-weight:600;">2000s</span><br>
            <span style="color:#94a3b8; font-size:0.8rem;">weaker / reversed relationship</span>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='border-top: 1px solid #1e293b; margin: 15px 0;'></div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style="font-size:0.85rem; color:#64748b; font-weight:600; margin-bottom:5px;">VALIDATION</div>
        <div style="color:#f8fafc; font-size:0.85rem;">100 × 100<br>Spatial Blocks</div>
        """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    # HORIZONTAL PIPELINE
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        st.markdown("""<div class="pipeline-item"><div class="pipeline-num">01</div><div class="pipeline-title">PHYSICAL CONDITIONS</div><div class="pipeline-desc">Meteorology, Topography, Soil</div></div>""", unsafe_allow_html=True)
    with p2:
        st.markdown("""<div class="pipeline-item"><div class="pipeline-num">02</div><div class="pipeline-title">PHYSICAL RISK</div><div class="pipeline-desc">AHP & Spatial ML Baseline</div></div>""", unsafe_allow_html=True)
    with p3:
        st.markdown("""<div class="pipeline-item"><div class="pipeline-num">03</div><div class="pipeline-title">SATELLITE RESPONSE</div><div class="pipeline-desc">Observed Landsat NDVI Stress</div></div>""", unsafe_allow_html=True)
    with p4:
        st.markdown("""<div class="pipeline-item"><div class="pipeline-num">04</div><div class="pipeline-title">TEMPORAL DIVERGENCE</div><div class="pipeline-desc">Changing relationship over time</div></div>""", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # WHAT DID WE FIND?
    st.markdown("<div class='section-title'>WHAT DID WE FIND?</div>", unsafe_allow_html=True)
    
    f1, f2, f3 = st.columns(3)
    
    with f1:
        st.markdown("""
        <div style="color:#64748b; font-family:'Space Grotesk'; font-weight:700;">01</div>
        <div style="color:#f8fafc; font-size:1rem; font-weight:600; margin-bottom:10px;">LIMITED EXPLANATORY POWER</div>
        <div style="color:#38bdf8; font-family:'Space Grotesk'; font-size:1.5rem; font-weight:700; margin-bottom:10px;">R² ≈ 0.13</div>
        <div style="color:#94a3b8; font-size:0.85rem; line-height:1.5; margin-bottom:15px;">Physical variables explain only a limited portion of observed agricultural vegetation stress under strict spatial validation.</div>
        """, unsafe_allow_html=True)
        
        # Mini Feature Importance Chart
        df_imp = pd.DataFrame({'F': ['SPI_12', 'Precip', 'LST'], 'I': [25.9, 20.7, 19.4]})
        fig_imp = go.Figure(go.Bar(x=df_imp['I'], y=df_imp['F'], orientation='h', marker_color='#38bdf8'))
        fig_imp.update_layout(height=120, margin=dict(l=0,r=0,t=0,b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showticklabels=False, showgrid=False), yaxis=dict(color='#cbd5e1', tickfont=dict(size=10)))
        st.plotly_chart(fig_imp, use_container_width=True, config={'displayModeBar': False})

    with f2:
        st.markdown("""
        <div style="color:#64748b; font-family:'Space Grotesk'; font-weight:700;">02</div>
        <div style="color:#f8fafc; font-size:1rem; font-weight:600; margin-bottom:10px;">PHYSICAL–OBSERVED MISMATCH</div>
        <div style="color:#94a3b8; font-size:0.85rem; line-height:1.5; margin-bottom:15px; height: 40px;">The physical baseline does not fully reproduce the satellite-observed response.</div>
        """, unsafe_allow_html=True)
        
        # Static thumbnail for mismatch
        st.markdown("""
        <div style="height: 120px; background: linear-gradient(90deg, #ef4444 0%, #080b12 50%, #38bdf8 100%); opacity: 0.6; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 0.8rem; color: #f8fafc; letter-spacing: 0.05em; border: 1px solid #1e293b;">
            OBSERVED MISMATCH GRADIENT
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top:10px; font-size:0.8rem; color:#38bdf8; font-weight:600;'>EXPLORE MISMATCH →</div>", unsafe_allow_html=True)

    with f3:
        st.markdown("""
        <div style="color:#64748b; font-family:'Space Grotesk'; font-weight:700;">03</div>
        <div style="color:#f8fafc; font-size:1rem; font-weight:600; margin-bottom:10px;">TEMPORAL DECOUPLING</div>
        <div style="color:#94a3b8; font-size:0.85rem; line-height:1.5; margin-bottom:15px; height: 40px;">The spatial relationship between physical drought risk and observed stress changes substantially through time.</div>
        """, unsafe_allow_html=True)
        
        # Mini Timeline Chart
        df_mini = pd.DataFrame({'Y': [1989, 1994, 2001, 2008], 'C': [-0.2, -0.26, 0.35, 0.01]})
        fig_mini = go.Figure(go.Scatter(x=df_mini['Y'], y=df_mini['C'], mode='lines+markers', line=dict(color='#cbd5e1', width=1), marker=dict(color=['#ef4444', '#ef4444', '#38bdf8', '#38bdf8'], size=8)))
        fig_mini.add_hline(y=0, line_dash="solid", line_color="#1e293b", line_width=1)
        fig_mini.update_layout(height=120, margin=dict(l=0,r=0,t=10,b=20), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False, tickfont=dict(size=10, color='#64748b')), yaxis=dict(showgrid=False, showticklabels=False))
        st.plotly_chart(fig_mini, use_container_width=True, config={'displayModeBar': False})
        
        st.markdown("<div style='margin-top:10px; font-size:0.8rem; color:#38bdf8; font-weight:600;'>EXPLORE 1985–2011 →</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE: 01 - PHYSICAL RISK
# ==============================================================================
elif page == "01 — PHYSICAL RISK":
    st.markdown("<div class='section-title'>PHYSICAL DROUGHT RISK</div>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.9rem; color:#94a3b8; margin-top:-1rem; margin-bottom:1.5rem;'>An AHP-based baseline representing environmental drought constraints.</p>", unsafe_allow_html=True)
    
    col_map, col_panel = st.columns([7.5, 2.5])
    
    with col_map:
        st.markdown("<div style='border: 1px solid #1e293b; border-radius: 8px; overflow: hidden;'>", unsafe_allow_html=True)
        risk_tif = BASE / "data" / "processed" / "risk_index_steep_riskier.tif"
        fmap, h = build_map(str(risk_tif), "YlOrRd", 0.0, 1.0, "Physical Risk", height=650)
        st_folium(fmap, height=h, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_panel:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem; color:#64748b; font-weight:600; letter-spacing:0.1em; margin-bottom:1rem;'>AHP COMPONENTS</div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div class="data-row"><div class="data-label">SPI-12</div><div class="data-val">Meteorological</div></div>
        <div class="data-row"><div class="data-label">Precipitation</div><div class="data-val">Climatological</div></div>
        <div class="data-row"><div class="data-label">LST</div><div class="data-val">Thermal</div></div>
        <div class="data-row"><div class="data-label">Slope</div><div class="data-val">Terrain</div></div>
        <div class="data-row"><div class="data-label">Elevation</div><div class="data-val">Terrain</div></div>
        <div class="data-row"><div class="data-label">Soil AWC</div><div class="data-val">Subsurface</div></div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='font-size:0.8rem; color:#64748b; font-weight:600; letter-spacing:0.1em; margin-top:2rem; margin-bottom:1rem;'>RISK DISTRIBUTION</div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style="display:flex; align-items:center; margin-bottom:8px;"><div style="width:12px; height:12px; background:#ffffcc; margin-right:10px;"></div><div style="font-size:0.85rem; color:#cbd5e1;">Low</div></div>
        <div style="display:flex; align-items:center; margin-bottom:8px;"><div style="width:12px; height:12px; background:#fd8d3c; margin-right:10px;"></div><div style="font-size:0.85rem; color:#cbd5e1;">Moderate</div></div>
        <div style="display:flex; align-items:center; margin-bottom:8px;"><div style="width:12px; height:12px; background:#e31a1c; margin-right:10px;"></div><div style="font-size:0.85rem; color:#cbd5e1;">High</div></div>
        <div style="display:flex; align-items:center; margin-bottom:8px;"><div style="width:12px; height:12px; background:#800026; margin-right:10px;"></div><div style="font-size:0.85rem; color:#cbd5e1;">Very High</div></div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE: 02 - PHYSICAL BASELINE
# ==============================================================================
elif page == "02 — PHYSICAL BASELINE":
    st.markdown("<div class='section-title'>PURE PHYSICAL BASELINE</div>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.9rem; color:#94a3b8; margin-top:-1rem; margin-bottom:2rem;'>How much observed agricultural stress can physical variables explain?</p>", unsafe_allow_html=True)
    
    col_metric, col_val = st.columns([1, 2])
    
    with col_metric:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem; color:#64748b; font-weight:600; letter-spacing:0.1em; margin-bottom:0.5rem;'>MODEL PERFORMANCE</div>", unsafe_allow_html=True)
        st.markdown("<div class='metric-value'>0.13</div>", unsafe_allow_html=True)
        st.markdown("<div style='color:#38bdf8; font-size:0.9rem; font-weight:600; margin-top:5px;'>R² / LIMITED EXPLANATORY POWER</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_val:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem; color:#64748b; font-weight:600; letter-spacing:0.1em; margin-bottom:1rem;'>SPATIAL VALIDATION</div>", unsafe_allow_html=True)
        
        v1, v2, v3 = st.columns([2, 0.5, 2])
        with v1:
            st.markdown("<div style='text-align:center; padding:15px; border:1px dashed #ef4444; border-radius:4px;'><div style='color:#ef4444; font-size:0.85rem; font-weight:600;'>RANDOM K-FOLD</div><div style='font-size:0.75rem; color:#94a3b8; margin-top:5px;'>High spatial leakage</div></div>", unsafe_allow_html=True)
        with v2:
            st.markdown("<div style='text-align:center; color:#64748b; line-height:60px;'>vs</div>", unsafe_allow_html=True)
        with v3:
            st.markdown("<div style='text-align:center; padding:15px; border:1px solid #38bdf8; background: rgba(56,189,248,0.05); border-radius:4px;'><div style='color:#38bdf8; font-size:0.85rem; font-weight:600;'>SPATIAL BLOCK CV (100x100)</div><div style='font-size:0.75rem; color:#cbd5e1; margin-top:5px;'>Strict geographic holdout</div></div>", unsafe_allow_html=True)
            
        st.markdown("</div>", unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_feat, col_excl = st.columns([2, 1])
    
    with col_feat:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem; color:#64748b; font-weight:600; letter-spacing:0.1em; margin-bottom:1rem;'>FEATURE IMPORTANCE</div>", unsafe_allow_html=True)
        
        df_imp = pd.DataFrame({
            'Feature': ['Aspect', 'Slope', 'Soil AWC', 'LST', 'Precipitation', 'SPI_12'],
            'Importance': [5.7, 10.1, 18.2, 19.4, 20.7, 25.9]
        })
        
        fig = px.bar(df_imp, x='Importance', y='Feature', orientation='h', text='Importance')
        fig.update_traces(marker_color='#38bdf8', texttemplate='%{text}%', textposition='outside', textfont=dict(color='#cbd5e1'))
        fig.update_layout(height=250, margin=dict(l=0,r=40,t=0,b=0), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""), yaxis=dict(title="", tickfont=dict(color='#f8fafc', size=12)))
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_excl:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem; color:#64748b; font-weight:600; letter-spacing:0.1em; margin-bottom:1rem;'>EXCLUDED FROM BASELINE</div>", unsafe_allow_html=True)
        st.markdown("""
        <div style="font-family: 'Space Grotesk', monospace; font-size: 0.85rem; color: #94a3b8; line-height: 2;">
        <span style="color: #ef4444;">✕</span> irrigation_access<br>
        <span style="color: #ef4444;">✕</span> distance_to_irrigation<br>
        <span style="color: #ef4444;">✕</span> distance_to_water<br>
        <span style="color: #ef4444;">✕</span> ndvi_dry
        </div>
        <div style="margin-top: 20px; font-size: 0.75rem; color: #64748b; border-top: 1px solid #1e293b; padding-top: 10px;">
        Excluded to prevent circularity and target leakage. The baseline must remain strictly physical.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE: 03 - PHYSICAL-OBSERVED MISMATCH
# ==============================================================================
elif page == "03 — PHYSICAL–OBSERVED MISMATCH":
    st.markdown("<div class='section-title'>PHYSICAL–OBSERVED MISMATCH</div>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="display: flex; align-items: center; justify-content: center; margin-bottom: 2rem; font-family: 'Space Grotesk', sans-serif;">
        <div style="font-size: 1.2rem; color: #f8fafc;">OBSERVED NDVI STRESS</div>
        <div style="font-size: 1.5rem; color: #64748b; margin: 0 20px;">−</div>
        <div style="font-size: 1.2rem; color: #f8fafc;">PHYSICAL EXPECTATION</div>
        <div style="font-size: 1.5rem; color: #64748b; margin: 0 20px;">=</div>
        <div style="font-size: 1.2rem; color: #38bdf8; font-weight: 700;">MISMATCH</div>
    </div>
    """, unsafe_allow_html=True)
    
    col_map, col_panel = st.columns([7.5, 2.5])
    
    with col_map:
        st.markdown("<div style='border: 1px solid #1e293b; border-radius: 8px; overflow: hidden;'>", unsafe_allow_html=True)
        gap_tif = BASE / "data" / "processed" / "resilience_gap.tif"
        fmap, h = build_map(str(gap_tif), "RdBu", -0.05, 0.05, "Mismatch", height=600)
        st_folium(fmap, height=h, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col_panel:
        st.markdown("<div class='panel'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:0.8rem; color:#64748b; font-weight:600; letter-spacing:0.1em; margin-bottom:1rem;'>DIVERGING SCALE</div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div style="border-left: 4px solid #ef4444; padding-left: 10px; margin-bottom: 20px;">
            <div style="color: #ef4444; font-weight: 600; font-size: 0.85rem;">MORE STRESS THAN EXPECTED</div>
            <div style="font-size: 0.8rem; color: #94a3b8;">Negative mismatch (Red)</div>
        </div>
        <div style="border-left: 4px solid #38bdf8; padding-left: 10px; margin-bottom: 30px;">
            <div style="color: #38bdf8; font-weight: 600; font-size: 0.85rem;">LESS STRESS THAN EXPECTED</div>
            <div style="font-size: 0.8rem; color: #94a3b8;">Positive mismatch (Blue)</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<div style='font-size:0.75rem; color:#f87171; border: 1px solid rgba(239,68,68,0.3); background: rgba(239,68,68,0.05); padding: 10px; border-radius: 4px; margin-bottom: 20px;'><b>DIAGNOSTIC NOTE:</b> This is not a direct measure of human impact.</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='font-size:0.75rem; color:#64748b; line-height:1.6;'><b>Possible contributors include:</b><br>• Unobserved physical factors<br>• Crop differences<br>• Land management<br>• Infrastructure<br>• Model limitations</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# PAGE: 04 - HISTORICAL DECOUPLING
# ==============================================================================
elif page == "04 — HISTORICAL DECOUPLING":
    st.markdown("<div class='section-title'>HISTORICAL DECOUPLING</div>", unsafe_allow_html=True)
    
    st.markdown("<div class='panel' style='padding: 2rem;'>", unsafe_allow_html=True)
    
    df_years = pd.DataFrame({
        'Year': ['1989', '1990', '1992', '1994', '2001', '2007', '2008'],
        'Correlation': [-0.2085, -0.0612, -0.4380, -0.2647, 0.3482, -0.0725, 0.0095]
    })
    
    fig = go.Figure()
    
    # 0 line
    fig.add_hline(y=0, line_dash="solid", line_color="#1e293b", line_width=2)
    
    # Shaded regions
    fig.add_vrect(x0=-0.5, x1=3.5, fillcolor="rgba(239, 68, 68, 0.05)", line_width=0, layer="below")
    fig.add_vrect(x0=3.5, x1=6.5, fillcolor="rgba(56, 189, 248, 0.05)", line_width=0, layer="below")
    
    colors = ['#38bdf8' if c > 0 else '#ef4444' for c in df_years['Correlation']]
    
    fig.add_trace(go.Bar(
        x=df_years['Year'],
        y=df_years['Correlation'],
        marker_color=colors,
        text=[f"r = {c:.4f}" for c in df_years['Correlation']],
        textposition='outside',
        textfont=dict(color='#f8fafc', size=13)
    ))
    
    fig.add_annotation(x=1.5, y=0.4, text="<b>1980s–1990s</b><br><span style='color:#ef4444'>STRONGER ALIGNMENT</span>", showarrow=False, font=dict(color="#f8fafc", size=14))
    fig.add_annotation(x=5, y=0.4, text="<b>2000s</b><br><span style='color:#38bdf8'>WEAKER / REVERSED</span>", showarrow=False, font=dict(color="#f8fafc", size=14))
    
    fig.update_layout(
        height=500,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=20, b=0),
        xaxis=dict(color='#cbd5e1', showgrid=False, tickfont=dict(size=14)),
        yaxis=dict(color='#64748b', gridcolor='#1e293b', zeroline=False, range=[-0.55, 0.55], title="Spatial Spearman correlation (r)")
    )
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center;">
        <div style="font-family: 'Space Grotesk', sans-serif; font-size: 2rem; color: #f8fafc; font-weight: 700; letter-spacing: 0.05em; margin-bottom: 10px;">TEMPORAL NON-STATIONARITY</div>
        <div style="font-size: 1.1rem; color: #94a3b8; max-width: 800px; margin: 0 auto; line-height: 1.6;">
            The same physical drought conditions are not associated with the same spatial vegetation response across time.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# FOOTER / METHODOLOGY / LIMITATIONS
# ==============================================================================
st.markdown("<hr>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)

with c1:
    st.markdown("<div style='font-size:0.75rem; color:#64748b; font-weight:700; letter-spacing:0.1em; margin-bottom:10px;'>DATA PROVENANCE</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.6;">
    • Landsat NDVI<br>
    • SPI-12 & Precipitation<br>
    • Land Surface Temp (LST)<br>
    • DEM (Slope, Elevation)<br>
    • Soil AWC<br>
    • CORINE Agricultural Mask
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown("<div style='font-size:0.75rem; color:#64748b; font-weight:700; letter-spacing:0.1em; margin-bottom:10px;'>SCIENTIFIC INTEGRITY</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.6;">
    <span style="color:#cbd5e1;">Terms used:</span> physical-observed mismatch, temporal divergence, temporal non-stationarity, observational evidence, limited explanatory power, diagnostic.<br><br>
    <span style="color:#ef4444;">Claims avoided:</span> causality, "irrigation caused resilience", "proved", successful prediction.
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown("<div style='font-size:0.75rem; color:#64748b; font-weight:700; letter-spacing:0.1em; margin-bottom:10px;'>METHODOLOGICAL LIMITATIONS</div>", unsafe_allow_html=True)
    st.markdown("""
    <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.6;">
    • Mismatch cannot be uniquely attributed to irrigation.<br>
    • Historical analysis may be affected by land-cover temporal consistency, crop-calendar changes, sensor differences, and unobserved physical variables.
    </div>
    """, unsafe_allow_html=True)
