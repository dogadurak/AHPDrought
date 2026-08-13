"""Konfigürasyon yükleme ve doğrulama testleri.

"Hiçbir sabit kod içine gömülmesin" kısıtının bekçisi burasıdır: config.yaml
bozulursa kod çalışmadan önce anlaşılır bir hata vermeli.
"""

from __future__ import annotations

import copy

import pytest
import yaml

from src.config import PROJECT_ROOT, ConfigError, load_config, load_json


@pytest.fixture
def raw_config():
    with (PROJECT_ROOT / "config.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _write(tmp_path, data):
    path = tmp_path / "config.yaml"
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, allow_unicode=True)
    return path


# --- Mevcut konfigürasyon ----------------------------------------------------


def test_project_config_loads():
    config = load_config()
    assert config.crs.startswith("EPSG:")
    assert config.resolution > 0
    assert len(config.criteria_order) == len(config['criteria'])


def test_every_criterion_is_in_the_ahp_matrix():
    config = load_config()
    assert set(config["criteria"]) == set(config.criteria_order)


def test_every_criterion_declares_a_risk_direction():
    config = load_config()
    for name in config.criteria_order:
        crit = config.criterion(name)
        assert "higher_is_riskier" in crit, f"{name}: risk yönü tanımsız"
        assert isinstance(crit["higher_is_riskier"], bool)
        assert "normalization" in crit, f"{name}: normalizasyon yöntemi tanımsız"


def test_worldcover_lookup_is_complete():
    """WorldCover'ın 11 sınıfının tamamı skor tablosunda karşılığını bulmalı."""
    config = load_config()
    lookup = load_json(config["data_sources"]["landcover"]["lookup_file"])

    worldcover_codes = {"10", "20", "30", "40", "50", "60", "70", "80", "90", "95", "100"}
    assert set(lookup["classes"]) == worldcover_codes

    for code, entry in lookup["classes"].items():
        score = entry["score"]
        assert score is None or 0.0 <= score <= 1.0, f"sınıf {code}: skor aralık dışı ({score})"

    # Cropland ana ilgi sınıfı: en yüksek skorlulardan biri olmalı
    scores = {c: e["score"] for c, e in lookup["classes"].items() if e["score"] is not None}
    assert scores["40"] >= 0.8
    assert scores["60"] == max(scores.values())


def test_paths_section_resolves():
    config = load_config()
    for key in ("data_raw", "data_processed", "outputs", "aoi_file", "grid_file"):
        assert config.resolve(key).is_absolute()


def test_unknown_path_key_raises():
    with pytest.raises(ConfigError, match="paths"):
        load_config().resolve("olmayan_yol")


# --- Senaryolar --------------------------------------------------------------


def test_default_scenario_is_applied():
    config = load_config()
    assert config.scenario == "steep_riskier"
    assert config.criterion("slope")["higher_is_riskier"] is True


def test_alternative_scenario_flips_slope_direction():
    config = load_config(scenario="flat_riskier")
    assert config.scenario == "flat_riskier"
    assert config.criterion("slope")["higher_is_riskier"] is False


def test_scenario_only_touches_its_own_criteria():
    steep = load_config(scenario="steep_riskier")
    flat = load_config(scenario="flat_riskier")

    for name in steep.criteria_order:
        if name == "slope":
            continue
        assert steep.criterion(name) == flat.criterion(name)


def test_unknown_scenario_raises():
    with pytest.raises(ConfigError, match="senaryosu tanımlı değil"):
        load_config(scenario="olmayan_senaryo")


# --- Senaryoya bağlı kriter yolları ------------------------------------------


def test_only_overridden_criteria_are_scenario_dependent():
    config = load_config()
    assert config.is_scenario_dependent("slope") is True
    for name in config.criteria_order:
        if name != "slope":
            assert config.is_scenario_dependent(name) is False, f"{name} senaryoya bağlı olmamalı"


def test_scenario_dependent_criterion_gets_distinct_paths():
    """Regresyon: iki senaryonun eğim katmanı AYNI dosyaya yazılıyordu.

    Sonuç: `flat_riskier` çalıştırması `steep_riskier`ın ürettiği slope.tif'i
    sessizce yeniden kullanıyor, iki senaryo aynı çıkıyor ve senaryo
    karşılaştırması anlamsız bir %100 uyum raporluyordu.
    """
    steep = load_config(scenario="steep_riskier").criterion_path("slope")
    flat = load_config(scenario="flat_riskier").criterion_path("slope")

    assert steep != flat
    assert "steep_riskier" in steep.name
    assert "flat_riskier" in flat.name


def test_scenario_independent_criteria_share_one_file():
    """Senaryodan etkilenmeyen katmanları çoğaltmanın anlamı yok."""
    steep = load_config(scenario="steep_riskier")
    flat = load_config(scenario="flat_riskier")

    for name in steep.criteria_order:
        if name == "slope":
            continue
        assert steep.criterion_path(name) == flat.criterion_path(name)
        assert "__" not in steep.criterion_path(name).name


def test_criterion_paths_are_unique_within_a_scenario():
    config = load_config()
    paths = [config.criterion_path(name) for name in config.criteria_order]
    assert len(set(paths)) == len(paths)


# --- Doğrulama hataları ------------------------------------------------------


def test_missing_section_raises(tmp_path, raw_config):
    broken = copy.deepcopy(raw_config)
    del broken["classification"]
    with pytest.raises(ConfigError, match="classification"):
        load_config(_write(tmp_path, broken))


def test_criterion_missing_from_matrix_order_raises(tmp_path, raw_config):
    broken = copy.deepcopy(raw_config)
    broken["ahp"]["criteria_order"].remove("aspect")
    with pytest.raises(ConfigError, match="aspect"):
        load_config(_write(tmp_path, broken))


def test_matrix_size_mismatch_raises(tmp_path, raw_config):
    broken = copy.deepcopy(raw_config)
    broken["ahp"]["matrix"] = [row[:-1] for row in broken["ahp"]["matrix"][:-1]]
    with pytest.raises(ConfigError, match=r"\d+x\d+ olmalı"):
        load_config(_write(tmp_path, broken))


def test_invalid_bbox_raises(tmp_path, raw_config):
    broken = copy.deepcopy(raw_config)
    broken["aoi"]["bbox_wgs84"] = [28.6, 38.2, 27.6, 38.7]  # ters
    with pytest.raises(ConfigError, match="Geçersiz bbox"):
        load_config(_write(tmp_path, broken))


def test_class_label_count_mismatch_raises(tmp_path, raw_config):
    broken = copy.deepcopy(raw_config)
    broken["classification"]["n_classes"] = 4
    with pytest.raises(ConfigError, match="n_classes"):
        load_config(_write(tmp_path, broken))


def test_missing_file_raises():
    with pytest.raises(ConfigError, match="bulunamadı"):
        load_config("olmayan_config.yaml")
