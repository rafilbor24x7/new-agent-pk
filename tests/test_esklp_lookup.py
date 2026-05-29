import shutil

import pandas as pd

from app.services.esklp_lookup import EsklpLookup


def test_esklp_lookup_finds_trade_name_with_atx_and_ftg(monkeypatch):
    monkeypatch.setenv("ESKLP_DIR", "data/esklp_test")
    lookup = EsklpLookup()

    result = lookup.search("Ибупрофен")

    assert result
    assert result[0]["mnn"] == "Ибупрофен"
    assert result[0]["form"] == "таблетки"
    assert result[0]["atx_code"] == "M01AE"
    assert result[0]["atx_name"] == "Ибупрофен"
    assert result[0]["ftg_name"] == "Нестероидные противовоспалительные препараты"


def test_esklp_lookup_searches_tn_when_smnn_is_invalid(tmp_path):
    shutil.copyfile("data/esklp_test/tn_smnn_test.xlsx", tmp_path / "tn_smnn_test.xlsx")
    pd.DataFrame({"wrong": ["value"]}).to_excel(tmp_path / "esklp_smnn_test.xlsx", index=False)

    lookup = EsklpLookup(tmp_path)
    result = lookup.search("Ибупрофен")

    assert lookup.smnn_load_errors
    assert result
    assert result[0]["mnn"] == "Ибупрофен"
    assert result[0]["atx_code"] is None
    assert result[0]["atx_name"] is None
    assert result[0]["ftg_name"] is None
