"""Adım 5 — Sürekli risk indeksinin 5 risk sınıfına ayrılması.

Varsayılan yöntem Jenks Natural Breaks: sınıf içi varyansı en aza indirir,
yani verinin kendi doğal kümelenmesini kullanır. Eşit aralık yöntemi, dağılım
çarpıksa (bu projede olduğu gibi) sınıfları dengesiz doldurur.

Jenks tüm piksellerde çalıştırılamayacak kadar pahalıdır (5,5 milyon hücre),
bu yüzden sabit tohumlu rastgele bir örneklem üzerinden hesaplanır — sonuç
tekrarlanabilirdir.
"""

from __future__ import annotations

import numpy as np

from .config import Config

METHODS = ("jenks", "equal_interval", "quantile")


def compute_breaks(
    values: np.ndarray,
    *,
    method: str = "jenks",
    n_classes: int = 5,
    sample_size: int = 100_000,
    seed: int = 0,
) -> np.ndarray:
    """Sınıf üst sınırlarını döndürür (uzunluk = n_classes).

    Son eleman her zaman verinin maksimumudur, böylece hiçbir piksel sınıf dışı
    kalmaz.
    """
    if method not in METHODS:
        raise ValueError(f"Bilinmeyen sınıflandırma yöntemi '{method}'. Seçenekler: {METHODS}")
    if n_classes < 2:
        raise ValueError(f"En az 2 sınıf gerekir, {n_classes} verildi")

    finite = np.asarray(values, dtype="float64")
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("Sınıflandırılacak geçerli değer yok")
    if np.unique(finite).size < n_classes:
        raise ValueError(
            f"Veride yalnızca {np.unique(finite).size} farklı değer var, "
            f"{n_classes} sınıf üretilemez"
        )

    if method == "equal_interval":
        edges = np.linspace(finite.min(), finite.max(), n_classes + 1)[1:]
        return edges.astype("float64")

    if method == "quantile":
        qs = np.linspace(0, 100, n_classes + 1)[1:]
        return np.percentile(finite, qs).astype("float64")

    return _jenks(finite, n_classes, sample_size, seed)


def _jenks(values: np.ndarray, n_classes: int, sample_size: int, seed: int) -> np.ndarray:
    import mapclassify

    rng = np.random.default_rng(seed)
    sample = values if values.size <= sample_size else rng.choice(values, sample_size, replace=False)

    # mapclassify.NaturalBreaks küme başlangıçlarını GLOBAL numpy RNG'sinden
    # çeker; tohumlanmazsa aynı veriyle iki çalıştırma farklı sınıf sınırları
    # üretir (bu projede ölçülen fark ~0.009 indeks birimi — sınıf sınırlarını
    # kaydırmaya yeter). Sınıf sınırları nihai haritayı tanımladığı için global
    # durumu geçici olarak sabitliyoruz ve sonra aynen geri veriyoruz.
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        classifier = mapclassify.NaturalBreaks(sample, k=n_classes)
    finally:
        np.random.set_state(state)

    breaks = np.asarray(classifier.bins, dtype="float64")

    # Örneklem maksimumu tüm verinin maksimumundan küçük olabilir; son sınırı
    # gerçek maksimuma çek ki hiçbir piksel sınıf dışında kalmasın.
    breaks[-1] = max(breaks[-1], float(values.max()))
    return breaks


def apply_breaks(risk: np.ndarray, breaks: np.ndarray, n_classes: int) -> np.ndarray:
    """Sürekli indeksi 1..n_classes sınıf kodlarına çevirir (geçersiz = 0)."""
    breaks = np.asarray(breaks, dtype="float64")
    if breaks.size != n_classes:
        raise ValueError(f"{n_classes} sınıf için {n_classes} sınır gerekir, {breaks.size} verildi")

    classes = np.zeros(risk.shape, dtype="uint8")
    valid = np.isfinite(risk)

    # np.digitize sağ-kapalı aralıklar üretir: (-inf, b0], (b0, b1], ...
    indices = np.digitize(risk[valid], breaks[:-1], right=True) + 1
    classes[valid] = np.clip(indices, 1, n_classes).astype("uint8")
    return classes


def classify_risk(config: Config, risk: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """config.yaml ayarlarıyla risk indeksini sınıflandırır.

    Returns:
        (sınıf raster'ı, sınıf sınırları)
    """
    cfg = config["classification"]
    breaks = compute_breaks(
        risk[np.isfinite(risk)],
        method=cfg["method"],
        n_classes=cfg["n_classes"],
        sample_size=cfg["sample_size"],
    )
    return apply_breaks(risk, breaks, cfg["n_classes"]), breaks


def class_summary(config: Config, classes: np.ndarray, breaks: np.ndarray) -> str:
    """Sınıf dağılımını okunur tabloya çevirir."""
    cfg = config["classification"]
    labels = cfg["labels"]
    cell_km2 = (config.resolution**2) / 1e6

    valid_total = int((classes > 0).sum())
    lines = [
        f"{'Sınıf':<6}{'Etiket':<14}{'Üst sınır':>11}{'Piksel':>12}{'Pay':>9}{'Alan (km²)':>13}",
        "-" * 65,
    ]
    lower = 0.0
    for code in range(1, cfg["n_classes"] + 1):
        count = int((classes == code).sum())
        upper = float(breaks[code - 1])
        lines.append(
            f"{code:<6}{labels[code]:<14}{upper:>11.4f}{count:>12,}"
            f"{f'%{100 * count / valid_total:.1f}':>9}{count * cell_km2:>13,.1f}"
        )
        lower = upper
    lines.append("-" * 65)
    lines.append(f"{'TOPLAM':<31}{valid_total:>12,}{'%100.0':>9}{valid_total * cell_km2:>13,.1f}")

    masked = int((classes == 0).sum())
    lines.append(f"\nMaskeli (yerleşim/su/veri boşluğu): {masked:,} piksel, {masked * cell_km2:,.1f} km²")
    return "\n".join(lines)


def kmeans_crosscheck(risk: np.ndarray, n_classes: int, *, sample_size: int = 100_000, seed: int = 0) -> float:
    """Bağımsız k-means sınıflandırmasıyla uyum oranı (0-1).

    Jenks tek boyutlu bir optimizasyon, k-means ise farklı bir amaç fonksiyonu
    kullanır. İkisinin büyük ölçüde aynı sınırlara varması, sınıflandırmanın
    yöntem seçimine değil verinin kendi yapısına dayandığını gösterir.
    """
    from sklearn.cluster import KMeans

    values = risk[np.isfinite(risk)]
    rng = np.random.default_rng(seed)
    sample = values if values.size <= sample_size else rng.choice(values, sample_size, replace=False)

    km = KMeans(n_clusters=n_classes, n_init=10, random_state=seed).fit(sample.reshape(-1, 1))
    # k-means küme etiketleri keyfi sırada gelir; merkez değerine göre sırala.
    order = np.argsort(km.cluster_centers_.ravel())
    remap = np.zeros(n_classes, dtype=int)
    remap[order] = np.arange(1, n_classes + 1)
    kmeans_classes = remap[km.labels_]

    jenks_breaks = compute_breaks(sample, method="jenks", n_classes=n_classes, sample_size=sample_size)
    jenks_classes = apply_breaks(sample, jenks_breaks, n_classes)

    return float((kmeans_classes == jenks_classes).mean())
