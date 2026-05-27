from app.services.esklp_lookup import EsklpLookup


def test_esklp_lookup_finds_trade_name(monkeypatch):
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    lookup = EsklpLookup()

    result = lookup.search("Ибупрофен")

    assert result
    assert result[0]["mnn"] == "Ибупрофен"
    assert result[0]["form"] == "таблетки"