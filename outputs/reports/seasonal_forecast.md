# Mevsimsel Öngörü — Kış Sonu Durumundan Yaz Stresi

## Soru neden yeniden kuruldu

İlk denemede "SPI-3'ten 3 ay sonraki SPI-3" soruldu ve beceri sıfır
çıktı. Bu bir veri bulgusu değil, kötü kurulmuş bir soruydu: ay *t* için
SPI-3 *t−2…t* penceresini toplar, *t+3* için *t+1…t+3*'ü — **iki pencere
hiç kesişmez**, paylaşılacak bilgi yoktur.

Fiziksel olarak anlamlı soru şudur: Akdeniz ikliminde yaz yağışsızdır,
dolayısıyla yaz bitki örtüsünü belirleyen şey o yazki yağış değil,
**kışın toprakta biriken sudur**. Öngörülebilirlik varsa oradadır.

## Kurgu

- **Öngörücüler** ((3, 4) ayları sonunda bilinir): yas_mevsim_yagisi, ilkbahar_yagisi, ilkbahar_toprak_nemi, ilkbahar_pdsi, ilkbahar_pet
- **Hedef** ((7, 8, 9) ayları): yaz soil
- **Yıl sayısı:** 68 (1958–2025)

Öngörücü ve hedef aylarının kesişmediği kod içinde denetlenir; kesişselerdi
hedeften öngörücüye bilgi sızar ve beceri yapay olarak yükselirdi.

## Öngörücülerin hedefle ilişkisi

```
Öngörücüler ((3, 4) ayları): yas_mevsim_yagisi, ilkbahar_yagisi, ilkbahar_toprak_nemi, ilkbahar_pdsi, ilkbahar_pet
Hedef ((7, 8, 9) ayları): yaz soil
Yıl sayısı: 68 (1958-2025)

Öngörücü                  hedefle r   Spearman
----------------------------------------------
yas_mevsim_yagisi             0.384      0.313
ilkbahar_yagisi               0.616      0.711
ilkbahar_toprak_nemi          0.769      0.824
ilkbahar_pdsi                 0.420      0.467
ilkbahar_pet                 -0.646     -0.735
```

## Beceri

```
Hedef : yaz soil  ((7, 8, 9) ayları)
Girdi : (3, 4) ayları sonunda bilinen durum
Egitim: 1958-2004   Test: 2005-2025  (kronolojik)

Yöntem / öngörücü                   n         r      RMSE    BS-iklim    BS-kalici
----------------------------------------------------------------------------------
iklimatoloji (eğitim ort.)         21     0.000     2.087       0.000        0.518
kalıcılık (geçen yaz)              21    -0.110     3.006      -1.075        0.000
yas_mevsim_yagisi                  21     0.125     2.047       0.038        0.536
ilkbahar_yagisi                    21     0.712     1.645       0.379        0.701
ilkbahar_toprak_nemi               21     0.669     1.555       0.445        0.732
ilkbahar_pdsi                      21     0.044     2.149      -0.061        0.489
ilkbahar_pet                       21     0.650     1.871       0.196        0.613
----------------------------------------------------------------------------------
BS = Beceri Skoru (1 - MSE/MSE_referans). 0'in alti referanstan kotu.
Bir ongorucunun HEM iklimatolojiyi HEM kaliciligi gecmesi gerekir.
```

## Sonuç

**En iyi öngörücü: `ilkbahar_toprak_nemi`**

| Ölçüt | Değer |
|---|---:|
| İklimatolojiye karşı beceri | +0.445 |
| Kalıcılığa karşı beceri | +0.732 |
| Test dönemi korelasyonu | +0.669 |
| Test yılı sayısı | 21 |

Bir öngörücünün işe yaradığını söyleyebilmek için **her iki** beceri
skorunun da pozitif olması gerekir: iklimatolojiyi geçmek yetmez,
geçen yılın tekrarını da geçmelidir.

## Sınırlılıklar

1. **Model kasten basit.** Tek değişkenli doğrusal regresyon. Amaç en iyi
   tahmini bulmak değil, fiziksel bağın öngörü değeri taşıyıp taşımadığını
   göstermek. Az sayıda yılla karmaşık model aşırı uyum üretir.
2. **Hedef, etkinin dolaylı ölçüsüdür.** Toprak nemi verim değildir.
3. **Dinamik iklim tahmini kullanılmadı.** ECMWF SEAS5 gibi ürünler
   ufku gerçekten uzatabilir ama API anahtarı gerektirir.