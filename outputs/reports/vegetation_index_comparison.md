# Bitki örtüsü indeksi karşılaştırması — NDVI vs EVI

```
HAM İNDEKS DEĞERLERİ
--------------------------------------------------------------------
  NDVI  -0.909 .. +0.961  medyan +0.447  ort +0.455  std 0.208
  EVI   -0.272 .. +0.911  medyan +0.285  ort +0.297  std 0.136

  Ham katmanlar arası Pearson r  : 0.9365
  Ham katmanlar arası Spearman ρ : 0.9561

RİSK HARİTASINA ETKİSİ
--------------------------------------------------------------------
  Risk indeksi ortalama farkı : 0.00974
  Risk indeksi maksimum farkı : 0.09921
  Aynı sınıfta kalan piksel   : %88.34
  En fazla 1 sınıf kayan      : %100.00

BAĞIMSIZ ÖLÇÜMLE UYUM (MODIS ET/PET)
--------------------------------------------------------------------
  Hangi indeksin ürettiği harita, modele hiç girmemiş buharlaşma
  oranıyla daha tutarlı? Daha güçlü (mutlak değerce büyük) negatif
  korelasyon daha iyidir.

  NDVI  ham katman ρ = +0.6478 | risk haritası ρ = -0.2833 | sınıf 1-5 ET/PET farkı = 0.0423 | monoton: evet
  EVI   ham katman ρ = +0.6210 | risk haritası ρ = -0.2380 | sınıf 1-5 ET/PET farkı = 0.0378 | monoton: evet

  Bağımsız ölçümle daha uyumlu: NDVI

  NOT: Fark küçükse indeks seçimi bu havzada belirleyici değildir;
  bu da raporlanmaya değer bir sonuçtur.
```
