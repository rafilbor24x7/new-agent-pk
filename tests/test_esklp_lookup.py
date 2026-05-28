from app.services.esklp_lookup import EsklpLookup


def test_esklp_lookup_finds_trade_name_with_atx_and_ftg(monkeypatch):
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    lookup = EsklpLookup()

    result = lookup.search("Ибупрофен")

    assert result
    assert result[0]["mnn"] == "Ибупрофен"
    assert result[0]["form"] == "таблетки"
    assert result[0]["atx_code"] == "M01AE"
    assert result[0]["atx_name"] == "Производные пропионовой кислоты"
    assert result[0]["ftg_name"] == "Нестероидные противовоспалительные препараты"