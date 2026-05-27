def test_project_bootstrap_imports():
    import fastapi
    import pandas
    import openpyxl
    import duckdb
    import openai
    import rapidfuzz

    assert fastapi
    assert pandas
    assert openpyxl
    assert duckdb
    assert openai
    assert rapidfuzz
