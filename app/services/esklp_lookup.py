from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from rapidfuzz import fuzz, process


DEFAULT_ESKLP_DIRS = (
    Path("data/esklp_test"),
    Path("tests/fixtures/esklp_test"),
)
COLUMN_ALIASES = {
    "trade_name": (
        "trade_name",
        "торговое наименование",
        "торговое название",
        "тн",
        "наименование лп",
    ),
    "mnn": (
        "mnn",
        "мнн",
        "международное непатентованное наименование",
    ),
    "form": (
        "form",
        "лекарственная форма",
        "форма выпуска",
        "форма",
    ),
    "dosage": (
        "dosage",
        "дозировка",
        "доза",
    ),
    "smnn_code": (
        "smnn_code",
        "код смнн",
        "код узла смнн",
        "смнн код",
    ),
}


class EsklpLookup:
    def __init__(self, esklp_dir: str | Path | None = None, score_cutoff: int = 75) -> None:
        self.esklp_dir = _resolve_esklp_dir(esklp_dir)
        self.score_cutoff = score_cutoff
        self.connection = duckdb.connect(database=":memory:")
        self._df = self._load_dataframe()
        self.connection.register("esklp_tn_df", self._df)
        self.connection.execute("CREATE TABLE esklp_tn AS SELECT * FROM esklp_tn_df")

    def search(self, trade_name: str, limit: int = 3) -> list[dict[str, Any]]:
        query = str(trade_name or "").strip()
        if not query or self._df.empty:
            return []

        choices = self._df["trade_name"].fillna("").astype(str).tolist()
        matches = process.extract(
            query,
            choices,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=self.score_cutoff,
            limit=limit,
        )

        results: list[dict[str, Any]] = []
        seen: set[int] = set()
        for _, score, index in matches:
            if index in seen:
                continue
            seen.add(index)
            row = self._df.iloc[index]
            results.append(
                {
                    "trade_name": _clean_value(row.get("trade_name")),
                    "mnn": _clean_value(row.get("mnn")),
                    "form": _clean_value(row.get("form")),
                    "dosage": _clean_value(row.get("dosage")),
                    "smnn_code": _clean_value(row.get("smnn_code")),
                    "score": round(float(score), 2),
                }
            )
        return results

    def _load_dataframe(self) -> pd.DataFrame:
        files = sorted(self.esklp_dir.glob("tn_smnn_*.xlsx"))
        if not files:
            return _empty_esklp_df()

        frames = [_read_esklp_file(path) for path in files]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return _empty_esklp_df()

        df = pd.concat(frames, ignore_index=True)
        df = df.dropna(subset=["trade_name"])
        df = df.drop_duplicates(subset=["trade_name", "mnn", "form", "dosage", "smnn_code"])
        return df.reset_index(drop=True)


def _resolve_esklp_dir(esklp_dir: str | Path | None) -> Path:
    if esklp_dir is not None:
        return Path(esklp_dir)

    env_dir = os.getenv("ESKLP_DIR")
    if env_dir:
        return Path(env_dir)

    for candidate in DEFAULT_ESKLP_DIRS:
        if candidate.exists():
            return candidate
    return DEFAULT_ESKLP_DIRS[0]


def _read_esklp_file(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, skiprows=4, dtype=str)
    if raw.empty:
        return _empty_esklp_df()

    columns = _map_columns(raw.columns)
    data: dict[str, pd.Series] = {}
    for target in COLUMN_ALIASES:
        source = columns.get(target)
        if source is None:
            data[target] = pd.Series([None] * len(raw), dtype="object")
        else:
            data[target] = raw[source]

    df = pd.DataFrame(data)
    for column in df.columns:
        df[column] = df[column].map(_clean_value)
    return df


def _map_columns(columns: pd.Index) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    normalized_columns = {column: _normalize_header(column) for column in columns}
    for target, aliases in COLUMN_ALIASES.items():
        for column, normalized in normalized_columns.items():
            if normalized in aliases or any(alias in normalized for alias in aliases):
                mapped[target] = column
                break
    return mapped


def _normalize_header(value: object) -> str:
    return str(value or "").strip().casefold().replace("ё", "е")


def _clean_value(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _empty_esklp_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["trade_name", "mnn", "form", "dosage", "smnn_code"])