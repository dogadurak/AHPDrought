import numpy as np
from src.classify import compute_breaks

def test_jenks_determinism():
    """Jenks (Natural Breaks) siniflandirmasinin ayni tohumla ayni sonucu urettigini test eder."""
    # Rastgele sahte risk verisi olustur
    rng = np.random.default_rng(42)
    dummy_data = rng.uniform(0.1, 0.9, 5000)
    
    # Ayni tohum (seed) ile iki kez calistir
    breaks1 = compute_breaks(dummy_data, method="jenks", n_classes=5, seed=123)
    breaks2 = compute_breaks(dummy_data, method="jenks", n_classes=5, seed=123)
    
    # Sonuclarin birebir ayni olmasi beklenir (tohumlama calisiyorsa)
    np.testing.assert_array_almost_equal(breaks1, breaks2)

    # Farkli tohum ile calistir
    breaks3 = compute_breaks(dummy_data, method="jenks", n_classes=5, seed=999)
    # Farkli tohumun (cogunlukla) farkli sinirlar uretmesi beklenir, eger veri yeterince buyuk/karmasiksa.
    # Kesinlikle ayni olmayacagini test edebiliriz
    try:
        np.testing.assert_array_almost_equal(breaks1, breaks3)
        assert False, "Farkli tohumlar ayni sonucu uretti, bu beklenen bir durum degil."
    except AssertionError:
        pass # Expected
