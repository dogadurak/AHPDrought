"""Ortak pytest yapılandırması.

Ağ gerektiren testler `@pytest.mark.network` ile işaretlenir ve:
  - bağlantı yoksa otomatik atlanır (bağlantı kontrolü TEMBEL: yalnızca ağ
    işaretli bir test gerçekten çalışacaksa yapılır, her pytest çağrısında
    değil),
  - `pytest -m "not network"` ile tamamen devre dışı bırakılabilir.

CI'ın asıl işi (`-m "not network"`) böylece dış servislerin erişilebilirliğine
bağlı olmadan koşar; ağ testleri ayrı, zamanlanmış bir işte çalışır.
"""

from __future__ import annotations

import functools

import pytest

_PROBE_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"


@functools.lru_cache(maxsize=1)
def network_available() -> bool:
    """Ağ erişimini bir kez kontrol eder ve sonucu önbelleğe alır."""
    import requests

    try:
        requests.head(_PROBE_URL, timeout=10)
        return True
    except Exception:
        return False


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "network" in item.keywords and not network_available():
        pytest.skip("ağ erişimi yok — ağ gerektiren test atlandı")
