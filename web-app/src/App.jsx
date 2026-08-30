import { useState } from 'react'
import { MapContainer, TileLayer, ImageOverlay, useMap } from 'react-leaflet'
import { Droplet, ThermometerSun, Leaf, AlertTriangle } from 'lucide-react'
import 'leaflet/dist/leaflet.css'
import './App.css'

function App() {
  const [activeTab, setActiveTab] = useState('map');
  
  // Bounds for the Gediz basin from README
  const mapBounds = [
    [38.2, 27.6], // bottom left
    [38.7, 28.6]  // top right
  ];

  return (
    <>
      <section className="hero-container">
        <h1 className="hero-title">Gediz Havzası<br/>Tarımsal Kuraklık Riski</h1>
        <p className="hero-subtitle">
          9 faktörlü Analitik Hiyerarşi Süreci (AHP) ile geliştirilen, yüksek çözünürlüklü ve 
          bilimsel doğrulamaya sahip kuraklık izleme ve risk tahmin platformu.
        </p>
        
        <div className="stats-grid">
          <div className="glass-panel stat-card">
            <Droplet size={40} color="var(--primary-glow)" />
            <div className="stat-value">4.842 km²</div>
            <div className="stat-label">Analiz Alanı</div>
          </div>
          <div className="glass-panel stat-card">
            <ThermometerSun size={40} color="#f59e0b" />
            <div className="stat-value">%11.0</div>
            <div className="stat-label">Çok Yüksek Risk</div>
          </div>
          <div className="glass-panel stat-card">
            <Leaf size={40} color="#10b981" />
            <div className="stat-value">9 Kriter</div>
            <div className="stat-label">AHP Çözünürlüğü</div>
          </div>
        </div>
      </section>

      <section className="section">
        <h2 className="section-title">Kuraklık Analiz Paneli</h2>
        
        <div className="dashboard-layout">
          {/* Map View */}
          <div className="glass-panel map-container">
            {activeTab === 'map' ? (
              <MapContainer 
                bounds={mapBounds} 
                zoomControl={true} 
                scrollWheelZoom={false}
                style={{ height: '100%', width: '100%', backgroundColor: 'var(--bg-color)' }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://carto.com/">CartoDB</a>'
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                />
                <ImageOverlay
                  bounds={mapBounds}
                  url="/figures/risk_map_steep_riskier.png"
                  opacity={0.8}
                />
              </MapContainer>
            ) : (
              <div className="map-placeholder" style={{
                backgroundImage: `url('/figures/${
                  activeTab === 'criteria' ? 'criteria_panel_steep_riskier.png' :
                  activeTab === 'time' ? 'spi_series.png' :
                  'summary_irrigation.png'
                }')`
              }}></div>
            )}
          </div>

          {/* Sidebar controls */}
          <div className="glass-panel dashboard-sidebar">
            <button 
              className={`glass-panel risk-level ${activeTab === 'map' ? 'active' : ''}`}
              style={{ borderColor: activeTab === 'map' ? 'var(--primary-glow)' : 'transparent', cursor: 'pointer' }}
              onClick={() => setActiveTab('map')}
            >
              <h3>Risk Haritası</h3>
            </button>
            <button 
              className={`glass-panel risk-level ${activeTab === 'criteria' ? 'active' : ''}`}
              style={{ borderColor: activeTab === 'criteria' ? 'var(--primary-glow)' : 'transparent', cursor: 'pointer' }}
              onClick={() => setActiveTab('criteria')}
            >
              <h3>AHP Kriterleri</h3>
            </button>
            <button 
              className={`glass-panel risk-level ${activeTab === 'time' ? 'active' : ''}`}
              style={{ borderColor: activeTab === 'time' ? 'var(--primary-glow)' : 'transparent', cursor: 'pointer' }}
              onClick={() => setActiveTab('time')}
            >
              <h3>68 Yıllık İklim Serisi</h3>
            </button>
            <button 
              className={`glass-panel risk-level ${activeTab === 'validation' ? 'active' : ''}`}
              style={{ borderColor: activeTab === 'validation' ? 'var(--primary-glow)' : 'transparent', cursor: 'pointer' }}
              onClick={() => setActiveTab('validation')}
            >
              <h3>Bulgular: Sulama Etkisi</h3>
            </button>
            
            <div className="info-card glass-panel" style={{marginTop: 'auto', backgroundColor: 'rgba(255,255,255,0.02)'}}>
              <AlertTriangle color="var(--secondary-glow)" size={24} />
              <h4>Önemli Bulgu</h4>
              <p style={{fontSize: '0.9rem', color: 'var(--text-muted)'}}>
                Sulu tarım alanları kurak yıllarda şebekeden uzak yerlere göre <b>10 kat daha az</b> etkilenmektedir. NDVI anomalisi doğrudan sulama yönetimini yansıtır.
              </p>
            </div>
          </div>
        </div>
      </section>
      
      <footer style={{textAlign: 'center', padding: '3rem', color: 'var(--text-muted)'}}>
        <p>AHP Tabanlı Tarımsal Kuraklık Risk Haritalama — Gediz Havzası &copy; 2026</p>
      </footer>
    </>
  )
}

export default App
