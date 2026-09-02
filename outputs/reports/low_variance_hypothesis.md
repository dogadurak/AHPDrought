# Düşük Değişkenlikli Kriter Hipotezinin Sınanması

**Etki ölçüsü:** `ndvi` · **Kapsam:** yalnızca arazi örtüsü 40 ·
**Kurak yıl eşiği:** SPI-12 <= -1.0

## Hipotez

Adım 13, risk haritasının gerçek kuraklıklarda gözlenen etkiyi öngörmediğini
gösterdi. En kolay açıklama: ağırlığın **%45.9'i**
havzada neredeyse hiç değişmeyen 3 kriterde
(`precipitation`, `soil_awc`, `lst`). Yüzdelik normalizasyon bu kriterlerin
küçük gerçek farkını 0-1 aralığına gerdiği için harita ayrım üretemiyor olabilir.

**Sınama:** bu kriterler çıkarılır, kalan ağırlıklar toplamı 1 olacak şekilde
yeniden ölçeklenir (özvektör oranları korunur), harita yeniden üretilir ve
Adım 13'ün sınaması aynen tekrarlanır.

## Ağırlıklar ve katman değişkenliği

`std`, normalize edilmiş (0-1) katmanın havza içi standart sapmasıdır — düşük
değer, kriterin ölçeğini kullanmadığı anlamına gelir.

| Kriter | Tam harita | Alt küme | std |
|---|---:|---:|---:|
| `irrigation_access` | 0.1782 | 0.3293 | 0.2394 |
| `ndvi_dry` | 0.1585 | 0.2928 | 0.2774 |
| `landcover` | 0.0843 | 0.1558 | 0.2826 |
| `distance_to_water` | 0.0523 | 0.0966 | 0.1345 |
| `slope` | 0.0425 | 0.0786 | 0.2888 |
| `aspect` | 0.0254 | 0.0469 | 0.3228 |
| `precipitation` | 0.2135 | — (çıkarıldı) | 0.3028 |
| `soil_awc` | 0.1336 | — (çıkarıldı) | 0.2433 |
| `lst` | 0.1117 | — (çıkarıldı) | 0.2743 |

## Sonuç

| Harita | Kriter | Kurak yıl ortalama Spearman rho | Normal yıl |
|---|---:|---:|---:|
| Tam | 9 | **-0.0228** | -0.0579 |
| Alt küme | 6 | **+0.0129** | -0.0822 |

**HÜKÜM: REDDEDİLDİ — kriterleri çıkarmak düzeltmedi, ilişki daha da zayıfladı**

Düşük değişkenlik teşhisi doğru — üç kriterin standart sapması gerçekten düşük.
Ama başarısızlığın sebebi o değil: kriterleri çıkarmak haritayı düzeltmiyor.
Bu, Adım 13'ün sonucunun kriter seçimine bağlı olmadığını gösterir ve
"yanlış kriterleri seçtiniz" itirazını eler.

Sınamanın eşiği Adım 13 ile aynıdır (rho <= -0.10); yalnızca sayının biraz
oynaması hipotezi desteklemek için yeterli sayılmaz.
