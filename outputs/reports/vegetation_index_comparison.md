# Bitki örtüsü indeksi karşılaştırması — NDVI vs EVI

```
HAM İNDEKS DEĞERLERİ
--------------------------------------------------------------------
  NDVI  -0.934 .. +0.962  medyan +0.451  ort +0.459  std 0.210
  EVI   -0.272 .. +0.917  medyan +0.288  ort +0.300  std 0.138

  Ham katmanlar arası Pearson r  : 0.9359
  Ham katmanlar arası Spearman ρ : 0.9561

RİSK HARİTASINA ETKİSİ
--------------------------------------------------------------------
  Risk indeksi ortalama farkı : 0.01329
  Risk indeksi maksimum farkı : 0.14038
  Aynı sınıfta kalan piksel   : %87.23
  En fazla 1 sınıf kayan      : %100.00

BAĞIMSIZ ÖLÇÜMLE UYUM (MODIS ET/PET)
--------------------------------------------------------------------
  Hangi indeksin ürettiği harita, modele hiç girmemiş buharlaşma
  oranıyla daha tutarlı? Daha güçlü (mutlak değerce büyük) negatif
  korelasyon daha iyidir.

  NDVI  ham katman ρ = +0.6471 | risk haritası ρ = -0.3309 | sınıf 1-5 ET/PET farkı = 0.0489 | monoton: evet
  EVI   ham katman ρ = +0.6181 | risk haritası ρ = -0.2826 | sınıf 1-5 ET/PET farkı = 0.0448 | monoton: evet

  Bağımsız ölçümle daha uyumlu: NDVI

  NOT: Fark küçükse indeks seçimi bu havzada belirleyici değildir;
  bu da raporlanmaya değer bir sonuçtur.
```
