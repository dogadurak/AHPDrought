"""Merkezi konfigürasyon yükleyici.

Projedeki hiçbir modül `config.yaml` dosyasını doğrudan açmaz; hepsi
`load_config()` üzerinden geçer. Böylece senaryo geçersiz kılmaları
(scenario overrides) ve yol çözümlemesi tek yerde yapılır.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"


class ConfigError(ValueError):
    """Konfigürasyon dosyası tutarsız veya eksik olduğunda fırlatılır."""


@dataclass(frozen=True)
class Config:
    """Doğrulanmış konfigürasyon. `raw` sözlüğüne köşeli parantezle erişilir."""

    raw: dict[str, Any]
    scenario: str
    path: Path

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    # --- sık kullanılan kısayollar -------------------------------------------

    @property
    def crs(self) -> str:
        return self.raw["grid"]["crs"]

    @property
    def resolution(self) -> float:
        return float(self.raw["grid"]["resolution_m"])

    @property
    def nodata(self) -> float:
        return float(self.raw["grid"]["nodata"])

    @property
    def criteria_order(self) -> list[str]:
        return list(self.raw["ahp"]["criteria_order"])

    def criterion(self, name: str) -> dict[str, Any]:
        try:
            return self.raw["criteria"][name]
        except KeyError as exc:
            raise ConfigError(f"'{name}' kriteri config.yaml içinde tanımlı değil") from exc

    def resolve(self, path_key: str) -> Path:
        """`paths` bloğundaki bir anahtarı mutlak yola çevirir."""
        try:
            rel = self.raw["paths"][path_key]
        except KeyError as exc:
            raise ConfigError(f"'{path_key}' yolu config.yaml -> paths altında yok") from exc
        return PROJECT_ROOT / rel

    def is_scenario_dependent(self, name: str) -> bool:
        """Bu kriterin değeri seçili senaryoya göre değişiyor mu?"""
        definitions = (self.raw.get("scenarios") or {}).get("definitions") or {}
        return any(
            name in (definition.get("criteria_overrides") or {})
            for definition in definitions.values()
        )

    def criterion_path(self, name: str) -> Path:
        """Bir kriter raster'ının yazılacağı/okunacağı yol.

        Senaryoya bağlı kriterler (eğim) dosya adında senaryo etiketi taşır.
        Taşımasalardı `flat_riskier` çalıştırması `steep_riskier`ın ürettiği
        `slope.tif`i sessizce yeniden kullanır, iki senaryo aynı çıkar ve
        senaryo karşılaştırması anlamsız bir %100 uyum raporlardı.

        Senaryodan bağımsız kriterler tek kopya tutulur — aynı veriyi senaryo
        sayısı kadar çoğaltmanın anlamı yok.
        """
        suffix = f"__{self.scenario}" if self.is_scenario_dependent(name) else ""
        return self.resolve("criteria") / f"{name}{suffix}.tif"


def load_config(
    path: str | Path | None = None,
    scenario: str | None = None,
) -> Config:
    """`config.yaml`'ı okur, senaryoyu uygular ve tutarlılığını doğrular.

    Args:
        path: Alternatif config dosyası (testler için).
        scenario: `scenarios.definitions` altındaki bir isim. None ise
            `scenarios.active` kullanılır.
    """
    cfg_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise ConfigError(f"Config dosyası bulunamadı: {cfg_path}")

    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    raw = copy.deepcopy(raw)
    active = _apply_scenario(raw, scenario)
    _validate(raw)
    return Config(raw=raw, scenario=active, path=cfg_path)


def _apply_scenario(raw: dict[str, Any], scenario: str | None) -> str:
    """Seçili senaryonun `criteria_overrides` bloğunu kriterlere işler."""
    scenarios = raw.get("scenarios") or {}
    definitions = scenarios.get("definitions") or {}
    active = scenario or scenarios.get("active")

    if active is None:
        return "default"
    if active not in definitions:
        raise ConfigError(
            f"'{active}' senaryosu tanımlı değil. Mevcut: {sorted(definitions)}"
        )

    for crit_name, overrides in (definitions[active].get("criteria_overrides") or {}).items():
        if crit_name not in raw["criteria"]:
            raise ConfigError(
                f"'{active}' senaryosu bilinmeyen '{crit_name}' kriterini geçersiz kılmaya çalışıyor"
            )
        raw["criteria"][crit_name].update(overrides)

    return active


def _validate(raw: dict[str, Any]) -> None:
    """Kod çalışmadan önce yakalanabilecek tutarsızlıkları kontrol eder."""
    for section in ("grid", "aoi", "criteria", "ahp", "classification", "paths"):
        if section not in raw:
            raise ConfigError(f"config.yaml içinde '{section}' bölümü eksik")

    order = raw["ahp"]["criteria_order"]
    criteria = raw["criteria"]

    missing = [name for name in order if name not in criteria]
    if missing:
        raise ConfigError(f"ahp.criteria_order'da olup criteria'da olmayan: {missing}")

    unused = [name for name in criteria if name not in order]
    if unused:
        raise ConfigError(
            f"criteria'da tanımlı ama ahp.criteria_order'da yer almayan: {unused}. "
            "AHP matrisi tüm kriterleri kapsamalı."
        )

    n = len(order)
    matrix = raw["ahp"]["matrix"]
    if len(matrix) != n or any(len(row) != n for row in matrix):
        raise ConfigError(
            f"AHP matrisi {n}x{n} olmalı, {len(matrix)}x{len(matrix[0]) if matrix else 0} bulundu"
        )

    bbox = raw["aoi"]["bbox_wgs84"]
    if len(bbox) != 4:
        raise ConfigError("aoi.bbox_wgs84 [min_lon, min_lat, max_lon, max_lat] olmalı")
    min_lon, min_lat, max_lon, max_lat = bbox
    if not (min_lon < max_lon and min_lat < max_lat):
        raise ConfigError(f"Geçersiz bbox: {bbox}")

    n_classes = raw["classification"]["n_classes"]
    labels = raw["classification"]["labels"]
    colors = raw["classification"]["colors"]
    if len(labels) != n_classes or len(colors) != n_classes:
        raise ConfigError(
            f"classification: n_classes={n_classes} ama {len(labels)} etiket / {len(colors)} renk var"
        )


def load_json(path: str | Path) -> dict[str, Any]:
    """Yardımcı: lookup tablolarını okumak için."""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)
