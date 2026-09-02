# Fiziksel Taban Çizgisi — Random Forest (`physical`)

**Soru:** Yalnızca fiziksel ve meteorolojik değişkenler, gözlenen tarımsal
stresi (NDVI anomalisi) ne kadar açıklayabiliyor?

**Kurgu:** 99,997 örnek · 100x100 piksellik
mekânsal bloklar (536 blok) · 5 katlı GroupKFold. Eğitim maskesi:
`agri`. Model: RandomForestRegressor (n_estimators=100,
max_depth=15, min_samples_leaf=5, random_state=42).

Mekânsal blok çapraz doğrulama, komşu piksellerin birbirine benzemesinden
doğan sızıntıyı (spatial leakage) engeller. Rastgele bölmeyle skor yapay
olarak yüksek çıkardı; buradaki sayı bu yüzden kasıtlı olarak muhafazakârdır.

## Kat bazında sonuçlar

| Kat | R² | RMSE | MAE |
|---|---:|---:|---:|
| 1 | +0.1167 | 0.0947 | 0.0665 |
| 2 | +0.1450 | 0.0949 | 0.0665 |
| 3 | +0.1506 | 0.0890 | 0.0622 |
| 4 | +0.1484 | 0.0860 | 0.0587 |
| 5 | +0.1019 | 0.0899 | 0.0617 |
| **ortalama** | **+0.1325** | **0.0909** | **0.0631** |
| standart sapma | 0.0196 | 0.0034 | 0.0030 |

## Özellik önemleri (katlar arası ortalama)

| Özellik | Önem |
|---|---:|
| `SPI_12_Dynamic` | %25.7 |
| `precipitation` | %20.8 |
| `lst` | %19.5 |
| `slope` | %16.0 |
| `soil_awc` | %13.9 |
| `aspect` | %4.0 |

## Yorum

R² ≈ 0.13: fiziksel değişkenler gözlenen stresin küçük bir kısmını
açıklıyor. Bu, modelin kötü kurulduğu anlamına gelmez — yoğun insan müdahalesi
olan (sulama altyapısı, kuyu erişimi, ürün deseni) bir tarım havzasında,
yalnızca fiziksel duyarlılıktan yola çıkarak parsel ölçeğinde stres öngörmenin
sınırını ölçüyor.

Özellik önemleri nedensellik göstermez: ağacın bölme tercihidir ve birbiriyle
ilişkili değişkenler arasında paylaşılır.

Model dosyası: `rf_drought_model_physical.joblib`
