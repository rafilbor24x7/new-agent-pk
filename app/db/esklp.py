import duckdb


def connect(path: str = ":memory:") -> duckdb.DuckDBPyConnection:
    return duckdb.connect(path)
