"""Adım 14 — Gelişmiş Makine Öğrenmesi (Spatial Random Forest) Testi.

Literatür destekli olarak, klasik i.i.d. Random Forest yerine:
1. Mekansal Otokorelasyon (X ve Y Koordinatları) modelde bloklanarak (GroupKFold) çözülür.
2. İklimsel Şiddet (SPI-12) dinamik bir özellik olarak eklenir.
3. Model A (Full) ve Model B (Pure Physical) olarak iki farklı konfigürasyon çalıştırılabilir.
"""

from __future__ import annotations

import argparse
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

from src.config import load_config
from src.grid import build_grid
from src.overlay import load_criteria
from src.historical import available_years, landsat_anomaly, severity_index
from src.fetch.common import resolve, interim_path
from src.fetch.climate_series import load_basin_climate_series
from src.grid import read_grid_aligned
from src.drought_index import spi


def create_spatial_blocks(x_coords, y_coords, block_size_pixels):
    """X ve Y koordinatlarını grid bloklarına ayırarak block_id üretir."""
    x_blocks = x_coords // block_size_pixels
    y_blocks = y_coords // block_size_pixels
    # Benzersiz bir block_id üretimi:
    max_x_blocks = np.max(x_blocks) + 1
    block_ids = y_blocks * max_x_blocks + x_blocks
    return block_ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gelişmiş Makine Öğrenmesi (RF) Testi")
    parser.add_argument("--config", default=None)
    parser.add_argument("--scenario", default=None)
    parser.add_argument("--model-type", choices=["full", "physical"], default="physical",
                        help="'full' (Model A) veya 'physical' (Model B)")
    parser.add_argument("--train-mask", choices=["all", "agri"], default="agri",
                        help="Train on all valid landcover ('all' - Exp A) or only agriculture ('agri' - Exp B)")
    parser.add_argument("--grid-size", type=int, default=100,
                        help="Spatial cross-validation block size in pixels (e.g. 50, 100, 200)")
    args = parser.parse_args(argv)

    config = load_config(args.config, scenario=args.scenario)
    grid = build_grid(config)

    print("=" * 80)
    print(f"ADIM 14 — SPATIAL RANDOM FOREST TESTİ (Model: {args.model_type.upper()})")
    print(f"Train Mask: {args.train_mask.upper()} | Grid Size: {args.grid_size}x{args.grid_size} pikseller")
    print("=" * 80)

    stack = load_criteria(config, grid)
    feature_names_full = list(stack.names)
    
    # Model A vs Model B feature selection
    if args.model_type == "physical":
        allowed_features = ["precipitation", "soil_awc", "slope", "aspect", "lst"]
        feature_indices = [i for i, name in enumerate(feature_names_full) if name in allowed_features]
        base_feature_names = [feature_names_full[i] for i in feature_indices]
    else:
        # Full model uses all except ndvi_dry (target leakage)
        feature_indices = [i for i, name in enumerate(feature_names_full) if name != "ndvi_dry"]
        base_feature_names = [feature_names_full[i] for i in feature_indices]
    
    # Koordinat matrislerini olustur (grid.width=sutun/X, grid.height=satir/Y)
    y_coords, x_coords = np.mgrid[0:grid.height, 0:grid.width]
    
    # Tarım maskesi (Corine kodu varsayılan 40 olarak historical'da kullanılıyor)
    agri_mask = None
    if args.train_mask == "agri":
        lc_path = interim_path(config, "landcover.tif")
        lc_codes = read_grid_aligned(lc_path, grid)
        agri_mask = (lc_codes == 40)

    source = "ndvi"
    years = available_years(config, source=source)
    if not years:
        raise SystemExit("Landsat anomalileri bulunamadı.")

    frame = load_basin_climate_series(config)
    spi12 = spi(frame["ppt"].dropna(), scale=12).values
    severity = severity_index(spi12, years)

    # SPI <= 0 olan tüm yılları dahil edelim (hafif, orta, şiddetli kuraklıklar)
    target_years = [y for y in years if severity[y] <= 0.0]
    if not target_years:
        raise SystemExit("Eğitim için yeterli kurak/yarı-kurak yıl bulunamadı.")
    
    rng = np.random.default_rng(42)
    sample_size = 100_000 // len(target_years)
    
    X_list, y_list, block_list = [], [], []
    
    for year in target_years:
        anomaly = landsat_anomaly(config, grid, year, years=years, source=source)
        
        valid = stack.valid_mask & np.isfinite(anomaly)
        if agri_mask is not None:
            valid = valid & agri_mask
            
        features = stack.data[feature_indices, :]
        features = features[:, valid].T
        
        # Spatial Coordinates and Block IDs
        f_x = x_coords[valid]
        f_y = y_coords[valid]
        blocks = create_spatial_blocks(f_x, f_y, args.grid_size)
        
        # Yılların karışmaması için block_id'ye yıl bilgisini ekleyebiliriz veya 
        # modelin aynı lokasyonu farklı yıllarda görmesi sorun yaratabilir. 
        # Güvenli olan, spatial bloku lokasyona göre yapmaktır.
        
        # Dinamik İklim (SPI-12)
        f_spi = np.full((features.shape[0], 1), severity[year])
        
        # Sadece Kriterler ve SPI birleştiriliyor. (X, Y'yi modele DOĞRUDAN vermiyoruz, 
        # çünkü ML modeli mutlak lokasyonu ezberlememeli, bloklar için saklıyoruz).
        features_extended = np.hstack([features, f_spi])
        target = anomaly[valid]
        
        if len(target) > sample_size:
            idx = rng.choice(len(target), sample_size, replace=False)
            features_extended = features_extended[idx]
            target = target[idx]
            blocks = blocks[idx]
            
        X_list.append(features_extended)
        y_list.append(target)
        block_list.append(blocks)

    X = np.vstack(X_list)
    y = np.concatenate(y_list)
    groups = np.concatenate(block_list)
    
    feature_names = base_feature_names + ["SPI_12_Dynamic"]
    
    print(f"\nEğitim verisi hazırlandı. Toplam {len(y)} örnek.")
    print(f"Kullanılan Özellikler ({len(feature_names)} adet): {feature_names}")

    print(f"\n[5-Fold GroupKFold Spatial CV ile Değerlendirme Başlıyor...]")
    gkf = GroupKFold(n_splits=5)
    
    rf = RandomForestRegressor(
        n_estimators=100, 
        max_depth=15, 
        min_samples_leaf=5, 
        n_jobs=-1, 
        random_state=42
    )

    r2_scores = []
    rmse_scores = []
    mae_scores = []
    importances_list = []

    fold = 1
    for train_idx, test_idx in gkf.split(X, y, groups=groups):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = y[train_idx], y[test_idx]
        
        rf.fit(X_train, y_train)
        preds = rf.predict(X_test)
        
        r2 = r2_score(y_test, preds)
        rmse = np.sqrt(mean_squared_error(y_test, preds))
        mae = mean_absolute_error(y_test, preds)
        
        r2_scores.append(r2)
        rmse_scores.append(rmse)
        mae_scores.append(mae)
        importances_list.append(rf.feature_importances_)
        
        print(f" Fold {fold} -> R2: {r2:+.4f}, RMSE: {rmse:.4f}, MAE: {mae:.4f}")
        fold += 1

    print("\n[GENEL SONUÇLAR]")
    print(f"Ortalama R^2 Skoru  : {np.mean(r2_scores):+.4f}")
    print(f"Ortalama RMSE       : {np.mean(rmse_scores):.4f}")
    print(f"Ortalama MAE        : {np.mean(mae_scores):.4f}")

    print("\n[FEATURE IMPORTANCES (Özellik Önemleri)]")
    avg_importances = np.mean(importances_list, axis=0)
    for name, imp in sorted(zip(feature_names, avg_importances), key=lambda x: x[1], reverse=True):
        print(f" - {name:<20}: %{imp*100:.1f}")
        
    print("\n[MODEL KAYDEDİLİYOR]")
    print("Tüm eğitim verisiyle (Final Model) eğitim yapılıyor...")
    final_rf = RandomForestRegressor(
        n_estimators=100, 
        max_depth=15, 
        min_samples_leaf=5, 
        n_jobs=-1, 
        random_state=42
    )
    final_rf.fit(X, y)
    
    out_dir = resolve(config["paths"]["data_processed"])
    out_dir.mkdir(parents=True, exist_ok=True)
    model_name = f"rf_drought_model_{args.model_type}.joblib"
    model_path = out_dir / model_name
    joblib.dump(final_rf, model_path)
    print(f"Model başarıyla kaydedildi: {model_path}")

    _write_report(
        config,
        args,
        feature_names=feature_names,
        r2=r2_scores,
        rmse=rmse_scores,
        mae=mae_scores,
        importances=avg_importances,
        n_samples=len(y),
        n_blocks=len(np.unique(groups)),
        model_path=model_path,
    )

    print(f"\nAdım 14 Tamamlandı ({args.model_type.upper()} Modeli).")
    return 0


def _write_report(config, args, *, feature_names, r2, rmse, mae, importances,
                  n_samples, n_blocks, model_path) -> None:
    """Sonuçları dosyaya yazar.

    NEDEN: bu skorlar bugüne kadar yalnızca konsola basılıyordu, yani "R² 0,13
    nereden geliyor" sorusuna açılacak bir dosya yoktu. Ayrıca kat bazında
    dağılım verilmeden ortalama R² tek başına yanıltıcıdır — beş katın biri
    negatifse bunu ortalama gizler.
    """
    out = resolve(config["paths"]["reports"]) / f"ml_baseline_{args.model_type}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    r2, rmse, mae = np.asarray(r2), np.asarray(rmse), np.asarray(mae)
    fold_rows = "\n".join(
        f"| {i} | {a:+.4f} | {b:.4f} | {c:.4f} |"
        for i, (a, b, c) in enumerate(zip(r2, rmse, mae), 1)
    )
    imp_rows = "\n".join(
        f"| `{n}` | %{v * 100:.1f} |"
        for n, v in sorted(zip(feature_names, importances), key=lambda t: -t[1])
    )

    body = f"""# Fiziksel Taban Çizgisi — Random Forest (`{args.model_type}`)

**Soru:** Yalnızca fiziksel ve meteorolojik değişkenler, gözlenen tarımsal
stresi (NDVI anomalisi) ne kadar açıklayabiliyor?

**Kurgu:** {n_samples:,} örnek · {args.grid_size}x{args.grid_size} piksellik
mekânsal bloklar ({n_blocks:,} blok) · 5 katlı GroupKFold. Eğitim maskesi:
`{args.train_mask}`. Model: RandomForestRegressor (n_estimators=100,
max_depth=15, min_samples_leaf=5, random_state=42).

Mekânsal blok çapraz doğrulama, komşu piksellerin birbirine benzemesinden
doğan sızıntıyı (spatial leakage) engeller. Rastgele bölmeyle skor yapay
olarak yüksek çıkardı; buradaki sayı bu yüzden kasıtlı olarak muhafazakârdır.

## Kat bazında sonuçlar

| Kat | R² | RMSE | MAE |
|---|---:|---:|---:|
{fold_rows}
| **ortalama** | **{r2.mean():+.4f}** | **{rmse.mean():.4f}** | **{mae.mean():.4f}** |
| standart sapma | {r2.std():.4f} | {rmse.std():.4f} | {mae.std():.4f} |

## Özellik önemleri (katlar arası ortalama)

| Özellik | Önem |
|---|---:|
{imp_rows}

## Yorum

R² ≈ {r2.mean():.2f}: fiziksel değişkenler gözlenen stresin küçük bir kısmını
açıklıyor. Bu, modelin kötü kurulduğu anlamına gelmez — yoğun insan müdahalesi
olan (sulama altyapısı, kuyu erişimi, ürün deseni) bir tarım havzasında,
yalnızca fiziksel duyarlılıktan yola çıkarak parsel ölçeğinde stres öngörmenin
sınırını ölçüyor.

Özellik önemleri nedensellik göstermez: ağacın bölme tercihidir ve birbiriyle
ilişkili değişkenler arasında paylaşılır.

Model dosyası: `{model_path.name}`
"""
    out.write_text(body, encoding="utf-8")
    print(f"Rapor: {out}")


if __name__ == "__main__":
    raise SystemExit(main())

