# Literatür ve Veri Kaynağı Künyeleri

Bu dosyadaki künyelerin tamamı Crossref/DataCite üzerinden doğrulanmıştır.
Doğrulama durumu her kaynağın yanında belirtilmiştir:

- **[künye ✓]** — yazar/yıl/dergi/DOI bibliyografik kayıttan doğrulandı
- **[içerik ✓]** — ilgili sayı veya iddia makalenin tam metninden okundu
- **[içerik ?]** — sayı özet/arama sonucundan alındı, **tam metinden teyit
  edilmeli** (yayıncı erişimi kapalıydı)

Tez/rapor yazımında `[içerik ?]` işaretli her satırın kaynağına erişip
doğrulamanız gerekir.

---

## 1. AHP metodolojisi

**Saaty, T. L. (1980).** *The Analytic Hierarchy Process: Planning, Priority
Setting, Resource Allocation.* McGraw-Hill, New York. **[künye ✓]**

Projede kullanılan üç unsurun kaynağı: Saaty 1–9 ikili karşılaştırma ölçeği,
ağırlıkların baskın özvektörden türetilmesi ve rastgele tutarlılık indeksi (RI)
tablosuyla CR ≤ 0.10 kabul eşiği. Uygulama: [`src/ahp.py`](../src/ahp.py).

**Aczél, J. & Saaty, T. L. (1983).** Procedures for synthesizing ratio
judgements. *Journal of Mathematical Psychology*, 27(1), 93–102.
<https://doi.org/10.1016/0022-2496(83)90028-7> **[künye ✓]**

Birden çok uzmanın yargılarının **geometrik ortalamayla** birleştirilmesinin
(AIJ) kaynağı. Aritmetik ortalama AHP matrisinin karşılıklılık özelliğini
(a_ji = 1/a_ij) bozar: 3 ve 1/3 diyen iki uzmanın ortalaması 1 olmalıyken 1.67
çıkar. Uygulama: [`src/ahp_survey.py`](../src/ahp_survey.py), doğrulaması
[`tests/test_ahp_survey.py`](../tests/test_ahp_survey.py).

---

## 2. Kuraklık için AHP uygulamaları — ağırlık karşılaştırması

Bu projenin `config.yaml → ahp.matrix` matrisinden türeyen ağırlıkları:

| Kriter | Bu proje |
|---|---:|
| Yağış | 0.279 |
| NDVI (kurak dönem) | 0.221 |
| LST | 0.170 |
| Arazi örtüsü | 0.125 |
| Su kaynağına mesafe | 0.107 |
| Eğim | 0.059 |
| Bakı | 0.038 |

### Karşılaştırma kaynakları

**Pandey, V. & Srivastava, P. K. (2019).** Integration of Microwave and
Optical/Infrared Derived Datasets for a Drought Hazard Inventory in a
Sub-Tropical Region of India. *Remote Sensing*, 11(4), 439.
<https://doi.org/10.3390/rs11040439> **[künye ✓] [içerik ?]**

> Bildirilen standartlaştırılmış ağırlıklar: yağış %44.5 > toprak nemi %25.2 >
> LST %15.8 > evapotranspirasyon %9.5 > NDVI %5.0.

Bu projenin ağırlık sıralamasıyla **yağışın baskın kriter olması** bakımından
uyumlu; ancak burada yağışın payı çok daha yüksek ve NDVI'ınki çok daha düşük.
Fark, çalışmanın toprak nemi (mikrodalga) verisi kullanabilmesinden kaynaklanıyor
olabilir — bu projede böyle bir katman yok, dolayısıyla NDVI daha fazla iş
yapıyor.

**Sarkar, S. K., Das, S., Rudra, R. R., Ekram, K. M. M., Haydar, M., Alam, E.,
Islam, M. K. & Islam, A. R. M. T. (2024).** Delineating the drought
vulnerability zones in Bangladesh. *Scientific Reports*, 14, 25564.
<https://doi.org/10.1038/s41598-024-75690-w> **[künye ✓] [içerik ✓]**

> Tarımsal kuraklık bileşeninin AHP ağırlıkları (Tablo 4): ekim yoğunluğu 0.237
> > sulama yöntemi 0.187 > arazi örtüsü 0.164 > NDVI 0.127 > toprak tipi 0.078
> > jeoloji 0.064 > toprak dokusu 0.063 > morfoloji 0.052 > eğrilik 0.028.
> Bildirilen tutarlılık oranı **CR = %5.8**.

İki noktada bu projeyi destekliyor: (a) arazi örtüsünün 0.12–0.16 bandında bir
ağırlık alması, (b) CR < 0.10 eşiğinin kabul ölçütü olarak kullanılması. Ayrıca
bir eksiği de gösteriyor: **sulama yöntemi ve ekim yoğunluğu bu çalışmada en
yüksek iki ağırlığı alıyor**, bu projede ise böyle bir katman yok (açık veriyle
elde edilemedi). Gediz'de tarımın sulamaya dayalı olduğu
[parsel eğrilerinden](../outputs/figures/ndvi_parcel_curves_2024.md) açıkça
görüldüğü için bu, sonucun bilinen ve raporlanması gereken bir sınırlılığıdır.

---

## 3. Kriterlerin risk yönleri

### Eğim — "dik yamaç = yüksek risk"

**Burka, A., Biazin, B. & Bewket, W. (2024).** Drought susceptibility modeling
with geospatial techniques and AHP model: a case of Bilate River Watershed,
Central Rift Valley of Ethiopia. *Geocarto International*, 39(1), 2395319.
<https://doi.org/10.1080/10106049.2024.2395319> **[künye ✓] [içerik ?]**

> Gerekçe: eğim arttıkça yüzey akışı hızlanır, yağmur suyunun infiltrasyonu
> azalır, kök bölgesi toprak nemi düşer; dolayısıyla dik yamaçlar düz araziden
> daha kurak-duyarlıdır.

Bu, projenin varsayılan `steep_riskier` senaryosunun dayanağıdır. Alternatif
`flat_riskier` senaryosu ("düz ovada drenaj zayıf, sığ toprak nemi yüksek
buharlaşmayla kaybedilir") için eşdeğer ağırlıkta bir kaynak **bulunamadı** —
bu yüzden proje tercihi gizlemek yerine iki senaryoyu da üretip farkı
raporluyor: piksellerin %76.2'si aynı sınıfta, %100'ü en fazla 1 sınıf kayıyor.

### NDVI ve LST birlikte kullanımı — ve sınırları

**Karnieli, A., Agam, N., Pinker, R. T., Anderson, M., Imhoff, M. L., Gutman,
G. G., Panov, N. & Goldberg, A. (2010).** Use of NDVI and Land Surface
Temperature for Drought Assessment: Merits and Limitations. *Journal of
Climate*, 23(3), 618–633. <https://doi.org/10.1175/2009JCLI2900.1>
**[künye ✓] [içerik ?]**

NDVI–LST ikilisinin kuraklık değerlendirmesinde neden işe yaradığını ve hangi
koşullarda yanıltıcı olduğunu tartışan referans çalışma. Bu projede ikisi ayrı
kriter olarak (0.221 ve 0.170 ağırlıkla) kullanılıyor; **negatif korelasyonlu
oldukları için kısmen örtüşen bilgi taşıdıkları** akılda tutulmalı.
[`tests/test_outputs.py`](../tests/test_outputs.py) içindeki
`test_criteria_are_not_duplicates` bu örtüşmeyi |r| < 0.97 eşiğiyle denetliyor.

### NDVI'ın kuraklık göstergesi olarak sınırı

**Jia, H., Chen, F., Zhang, J. & Du, E. (2020).** Vulnerability Analysis to
Drought Based on Remote Sensing Indexes. *International Journal of
Environmental Research and Public Health*, 17(20), 7660.
<https://doi.org/10.3390/ijerph17207660> **[künye ✓] [içerik ✓]**

> EVI, kuraklık duyarlılığını göstermede NDVI'dan bir miktar daha başarılı
> bulunmuş (R² = 0.61 vs 0.59).

Bu proje NDVI kullanıyor; EVI'ye geçiş küçük ama ölçülebilir bir iyileşme
sağlayabilir. Sentinel-2'de mavi bant (B02) mevcut olduğundan bu, ileride
yapılabilecek somut bir geliştirmedir.

---

## 4. Pilot bölge seçiminin dayanağı

**Kumanlioglu, A. A. (2019).** Characterizing meteorological and hydrological
droughts: A case study of the Gediz River Basin, Turkey. *Meteorological
Applications*, 27(1), e1857. <https://doi.org/10.1002/met.1857>
**[künye ✓] [içerik ?]**

> **Demirköprü Barajı'nı besleyen üst havzalarda** SPI/SPEI ile meteorolojik,
> SRI ile hidrolojik kuraklık karakterize edilmiş. 1984 öncesi yaş dönemlerin
> baskın olduğu, sonrasında kurak dönemlerin sıklaştığı ve uzadığı; 2000
> sonrasında sıcaklık artışına bağlı potansiyel evapotranspirasyon kaybının
> kuraklık olaylarındaki etkisinin arttığı bulunmuş.

Pilot bölge seçimini doğrudan destekliyor: Gediz Havzası'nın Demirköprü
membaı, kuraklığın literatürde belgelenmiş olduğu bir alan. Bu proje aynı
bölgeye **mekânsal** bir risk katmanı ekliyor — Kumanlioglu'nun istasyon
bazlı zaman serisi analizinin tamamlayıcısı olarak.

---

## 5. Yöntemsel araçlar

**Horn, B. K. P. (1981).** Hill shading and the reflectance map. *Proceedings
of the IEEE*, 69(1), 14–47. <https://doi.org/10.1109/PROC.1981.11918>
**[künye ✓]**

Eğim ve bakının 3×3 pencereden hesaplandığı Horn operatörünün kaynağı — GDAL,
QGIS ve ArcGIS'in varsayılan yöntemi. Uygulama:
[`src/criteria/terrain.py`](../src/criteria/terrain.py), doğrulaması
[`tests/test_terrain.py`](../tests/test_terrain.py) (bilinen eğimli düzlemlerde
analitik sonuçla karşılaştırma).

**Jenks, G. F. (1967).** The Data Model Concept in Statistical Mapping.
*International Yearbook of Cartography*, 7, 186–190. **[künye ✓]**

Sınıf içi varyansı en aza indiren doğal kırılma yöntemi.
[`mapclassify.NaturalBreaks`](https://pysal.org/mapclassify/) üzerinden
kullanılıyor.

---

## 6. Veri kaynakları

**Copernicus DEM GLO-30** — European Space Agency / Airbus Defence and Space.
Microsoft Planetary Computer koleksiyonu `cop-dem-glo-30`.
<https://planetarycomputer.microsoft.com/dataset/cop-dem-glo-30>

**Sentinel-2 Level-2A** — European Space Agency, Copernicus Programme.
Koleksiyon `sentinel-2-l2a`.
<https://planetarycomputer.microsoft.com/dataset/sentinel-2-l2a>

> **Baseline 04.00 radyometrik offset'i.** 25 Ocak 2022'den itibaren üretilen
> L2A ürünlerinde tüm bantlara `BOA_ADD_OFFSET = −1000` uygulanır. Planetary
> Computer bu offset'i geri almadan sunar. Ürün tanımı:
> <https://sentiwiki.copernicus.eu/web/s2-products>
> Projede item bazında `s2:processing_baseline` özelliğine göre düzeltiliyor
> ([`src/fetch/sentinel2.py`](../src/fetch/sentinel2.py)).

**Zanaga, D., Van De Kerchove, R., Daems, D., De Keersmaecker, W., Brockmann,
C., Kirches, G., et al. (2022).** *ESA WorldCover 10 m 2021 v200.* Zenodo.
<https://doi.org/10.5281/zenodo.7254221> **[künye ✓]**

Sınıf kodlarının kuraklık duyarlılık skoruna dönüşümü:
[`lookups/worldcover_susceptibility.json`](../lookups/worldcover_susceptibility.json).
**Bu skorlar literatürden alınmadı, bu projede gerekçelendirilerek atandı** —
her sınıfın skoru dosyada kök derinliği ve tarımsal maruziyet ekseninde
açıklanıyor. Uzman görüşüyle revize edilmeye açıktır.

**MODIS MYD11A2 v061 (Aqua, 8 günlük LST/Emissivity, 1 km)** — Wan, Z., Hook,
S. & Hulley, G., NASA EOSDIS Land Processes DAAC.
<https://doi.org/10.5067/MODIS/MYD11A2.061>

> Koleksiyon `modis-11A2-061` hem Terra (MOD11A2, ~10:30 yerel geçiş) hem Aqua
> (MYD11A2, ~13:30) ürünlerini içerir. Proje Aqua'yı kullanır: öğleden sonraki
> geçiş günlük maksimum yüzey sıcaklığına ve termal strese daha yakındır.

**Funk, C., Peterson, P., Landsfeld, M., Pedreros, D., Verdin, J., Shukla, S.,
Husak, G., Rowland, J., Harrison, L., Hoell, A. & Michaelsen, J. (2015).** The
climate hazards infrared precipitation with stations — a new environmental
record for monitoring extremes. *Scientific Data*, 2, 150066.
<https://doi.org/10.1038/sdata.2015.66> **[künye ✓]**

CHIRPS v2.0 aylık global yağış, ~0.05° (~5.5 km). Bu AOI'yi yaklaşık 20×10
hücreyle kapladığı için katman **bölgesel gradyan** taşır, yerel detay değil.

**Poggio, L., de Sousa, L. M., Batjes, N. H., Heuvelink, G. B. M., Kempen, B.,
Ribeiro, E. & Rossiter, D. (2021).** SoilGrids 2.0: producing soil information
for the globe with quantified spatial uncertainty. *SOIL*, 7(1), 217–240.
<https://doi.org/10.5194/soil-7-217-2021> **[künye ✓]**

Toprak yarayışlı su kapasitesi `wv0033 − wv1500` (tarla kapasitesi − solma
noktası) olarak 0–30 cm kök bölgesi için hesaplanıyor, katmanlar
kalınlıklarıyla ağırlıklı ortalanıyor. ISRIC WCS servisi, 250 m, kayıt
gerektirmez. Ölçülen değerler: 0.064–0.163 cm³/cm³ (ortalama 0.114).

**Mu, Q., Zhao, M. & Running, S. W. (2011).** Improvements to a MODIS global
terrestrial evapotranspiration algorithm. *Remote Sensing of Environment*,
115(8), 1781–1800. <https://doi.org/10.1016/j.rse.2011.02.019> **[künye ✓]**

MOD16 evapotranspirasyon algoritmasının kaynağı. Bu projede **kriter olarak
değil, bağımsız doğrulama değişkeni olarak** kullanılıyor: ET/PET oranı ayrı
bir Penman-Monteith modelinden gelir ve projedeki hiçbir kriter onun girdisi
değildir. Tek dolaylı bağ MOD16'nın MODIS LAI/FPAR kullanmasıdır — bitki
örtüsüyle akrabalığı sıfır değil, bu yüzden "tamamen bağımsız" denmiyor.
Ölçülen: ET 441 mm/yıl, PET 1653 mm/yıl, oran 0.132–0.826.

**OpenStreetMap** — © OpenStreetMap katılımcıları, Open Database License (ODbL).
<https://www.openstreetmap.org/copyright>

> **Sulama katmanının sınırı.** Sulama erişimi kriteri OSM'deki
> `waterway=canal/ditch/drain` ağından (237 km) türetilir. Bu, DSİ'nin resmî
> komuta alanı DEĞİLDİR: OSM'de yalnızca ana kanallar haritalıdır, tersiyer
> şebeke büyük ölçüde eksiktir. Kriter bu yüzden log uzayında normalize edilir
> — mutlak mesafeler sistematik olarak fazla çıkar, ama sıralama anlamlı kalır.
> `man_made=pipeline` bilerek dışarıda bırakıldı: OSM'de bu etiket petrol ve
> doğalgaz hatları için de kullanılır.

---

## 7. Henüz kapatılmamış boşluklar

### Kapatılanlar

- ~~Sulama katmanı~~ → OSM kanal ağından vekil kriter eklendi (ağırlık 0.178).
  **Ama vekil, resmî DSİ komuta alanı değil** — aşağıya bkz.
- ~~Toprak verisi~~ → SoilGrids yarayışlı su kapasitesi eklendi (0.134).
- ~~Bağımsız doğrulama~~ → MODIS ET/PET eklendi. Tam bağımsız değil (MOD16
  MODIS LAI/FPAR kullanır) ve saha verisinin yerini tutmaz.
- ~~Uzman anketi altyapısı~~ → [`src/ahp_survey.py`](../src/ahp_survey.py) form
  üretir, uzman başına CR denetler, geometrik ortalamayla birleştirir.

### Hâlâ açık

1. **DSİ resmî sulama şebeke sınırı.** Mevcut kriter OSM'den türetilen bir
   vekildir; OSM'de tersiyer kanallar eksiktir. Resmî komuta alanı poligonu
   edinilirse bu kriter doğrudan onunla değiştirilmelidir — bu, projedeki
   tek en büyük belirsizlik kaynağıdır.
2. **Saha doğrulaması.** TÜİK ilçe bazında verim istatistikleri, MGM istasyon
   bazlı SPI/SPEI serileri, yüksek risk sınıfından rastgele parsellerin yerinde
   kontrolü. Hiçbirinin açık API'si yok.
   Ayrıntı: [`validation_report.md`](../outputs/reports/validation_report.md).
3. **Uzman anketinin fiilen yapılması.** Araç hazır, anket yapılmadı. Mevcut
   matris yukarıdaki literatürdeki sıralamayı temsil eden, yazar tarafından
   kurulmuş bir başlangıç setidir.
4. **Ekim yoğunluğu / ürün deseni.** Sarkar ve ark. (2024) bu kritere 0.237 ile
   en yüksek ağırlığı veriyor. Türkiye'de ilçe bazında TÜİK'te var, mekânsal
   (parsel bazlı) açık veri yok.
