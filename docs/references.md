# Literatür ve Veri Kaynağı Künyeleri

Bu dosya Adım 9'da tamamlanacaktır. Aşağıdaki başlıklar altında, `config.yaml`
içinde alınan her metodolojik kararın dayanağı tam atıfla verilecektir.

## 1. AHP metodolojisi

- Saaty, T. L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.
  → Saaty 1-9 ölçeği, özvektör yöntemi, Random Index tablosu ve CR ≤ 0.10 eşiği.

**Doldurulacak:** Kuraklık/su kaynakları alanında AHP uygulayan, ikili
karşılaştırma matrisinin başlangıç değerlerine dayanak oluşturan makaleler.

## 2. Kriter seçimi ve risk yönleri

**Doldurulacak — her satır için bir atıf:**

| Kriter | Verilen risk yönü | Dayanak |
|---|---|---|
| Yağış | Az yağış → yüksek risk | |
| NDVI | Düşük NDVI → yüksek risk | |
| LST | Yüksek LST → yüksek risk | |
| Arazi örtüsü | Lookup skorları (`lookups/worldcover_susceptibility.json`) | |
| Su kaynağına mesafe | Uzak → yüksek risk | |
| Eğim (steep_riskier) | Dik → yüksek risk | |
| Eğim (flat_riskier) | Düz → yüksek risk | |
| Bakı | Güney → yüksek risk | |

## 3. Veri kaynakları

- **Copernicus DEM GLO-30** — ESA / Airbus. Microsoft Planetary Computer
  koleksiyonu: `cop-dem-glo-30`.
- **Sentinel-2 L2A** — ESA Copernicus. Koleksiyon: `sentinel-2-l2a`.
- **ESA WorldCover v200 (2021)** — Zanaga, D. et al. (2022). *ESA WorldCover
  10 m 2021 v200*. Koleksiyon: `esa-worldcover`.
- **MODIS MOD11A2 v061 (LST)** — Wan, Z., Hook, S., Hulley, G. NASA LP DAAC.
  Koleksiyon: `modis-11A2-061`.
- **CHIRPS v2.0** — Funk, C. et al. (2015). *The climate hazards infrared
  precipitation with stations*. Scientific Data, 2, 150066.
- **OpenStreetMap** — © OpenStreetMap katılımcıları, ODbL lisansı.

## 4. Doğrulama kaynakları (Adım 7)

**Doldurulacak:** TÜİK bitkisel üretim / verim istatistikleri, DSİ veya
Meteoroloji Genel Müdürlüğü kuraklık indeksi yayınları, Gediz Havzası üzerine
yapılmış mevcut kuraklık çalışmaları.
