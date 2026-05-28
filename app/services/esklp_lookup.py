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
TN_COLUMN_ALIASES = {
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
        "стандартизованное мнн",
    ),
    "form": (
        "form",
        "лекарственная форма",
        "стандартизованная лекарственная форма",
        "форма выпуска",
        "форма",
    ),
    "dosage": (
        "dosage",
        "дозировка",
        "стандартизованная дозировка",
        "доза",
    ),
    "smnn_code": (
        "smnn_code",
        "код смнн",
        "код узла смнн",
        "смнн код",
    ),
}
SMNN_POSITION_COLUMNS = {
    "smnn_code": 1,
    "ftg_name": 12,
    "atx_code": 13,
    "atx_name": 14,
}
ESKLP_COLUMNS = [
    "trade_name",
    "mnn",
    "form",
    "dosage",
    "smnn_code",
    "atx_code",
    "atx_name",
    "ftg_name",
]
SMNN_COLUMNS = ["smnn_code", "atx_code", "atx_name", "ftg_name"]


class EsklpLookup:
    def __init__(self, esklp_dir: str | Path | None = None, score_cutoff: int = 75) -> None:
        self.esklp_dir = _resolve_esklp_dir(esklp_dir)
        self.score_cutoff = score_cutoff
        self.connection = duckdb.connect(database=":memory:")
        self._tn_df = self._load_tn_dataframe()
        self._smnn_df = self._load_smnn_dataframe()
        self.connection.register("esklp_tn_df", self._tn_df)
        self.connection.register("esklp_smnn_df", self._smnn_df)
        self.connection.execute("CREATE TABLE esklp_tn AS SELECT * FROM esklp_tn_df")
        self.connection.execute("CREATE TABLE esklp_smnn AS SELECT * FROM esklp_smnn_df")
        self._df = self.connection.execute(
            """
            SELECT
                tn.trade_name,
                tn.mnn,
                tn.form,
                tn.dosage,
                tn.smnn_code,
                smnn.atx_code,
                smnn.atx_name,
                smnn.ftg_name
            FROM esklp_tn tn
            LEFT JOIN esklp_smnn smnn USING (smnn_code)
            """
        ).fetch_df()

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
            item = {column: _clean_value(row.get(column)) for column in ESKLP_COLUMNS}
            item["score"] = round(float(score), 2)
            results.append(item)
        return results

    def _load_tn_dataframe(self) -> pd.DataFrame:
        files = sorted(self.esklp_dir.glob("tn_smnn_*.xlsx"))
        if not files:
            return _empty_tn_df()

        frames = [_read_tn_file(path) for path in files]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return _empty_tn_df()

        df = pd.concat(frames, ignore_index=True)
        df = df.dropna(subset=["trade_name"])
        df = df.drop_duplicates(subset=["trade_name", "mnn", "form", "dosage", "smnn_code"])
        return df.reset_index(drop=True)

    def _load_smnn_dataframe(self) -> pd.DataFrame:
        files = sorted(self.esklp_dir.glob("esklp_smnn_*.xlsx"))
        if not files:
            return _empty_smnn_df()

        frames = [_read_smnn_file(path) for path in files]
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            return _empty_smnn_df()

        df = pd.concat(frames, ignore_index=True)
        df = df.dropna(subset=["smnn_code"])
        df = df.drop_duplicates(subset=["smnn_code"])
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


def _read_tn_file(path: Path) -> pd.DataFrame:
    raw = _read_esklp_excel(path, "tn_smnn")
    if raw.empty:
        return _empty_tn_df()

    columns = _map_columns(raw.columns, TN_COLUMN_ALIASES)
    data: dict[str, pd.Series] = {}
    for target in TN_COLUMN_ALIASES:
        source = columns.get(target)
        data[target] = raw[source] if source is not None else pd.Series([None] * len(raw), dtype="object")

    df = pd.DataFrame(data)
    for column in df.columns:
        df[column] = df[column].map(_clean_value)
    return df


def _read_smnn_file(path: Path) -> pd.DataFrame:
    raw = _read_esklp_excel(path, "esklp_smnn")
    if raw.empty:
        return _empty_smnn_df()

    data: dict[str, pd.Series] = {}
    for target, index in SMNN_POSITION_COLUMNS.items():
        data[target] = raw.iloc[:, index] if len(raw.columns) > index else pd.Series([None] * len(raw), dtype="object")

    df = pd.DataFrame(data)
    for column in df.columns:
        df[column] = df[column].map(_clean_value)
    return df[SMNN_COLUMNS]


def _read_esklp_excel(path: Path, sheet_prefix: str) -> pd.DataFrame:
    sheet_name = _find_sheet_name(path, sheet_prefix)
    return pd.read_excel(path, sheet_name=sheet_name, skiprows=4, dtype=str)


def _find_sheet_name(path: Path, sheet_prefix: str) -> str | int:
    excel = pd.ExcelFile(path)
    for sheet_name in excel.sheet_names:
        if sheet_name.casefold().startswith(sheet_prefix.casefold()):
            return sheet_name
    return 0


def _map_columns(columns: pd.Index, aliases_by_target: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    normalized_columns = {column: _normalize_header(column) for column in columns}
    for target, aliases in aliases_by_target.items():
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


def _empty_tn_df() -> pd.DataFrame:
    return pd.DataFrame(columns=["trade_name", "mnn", "form", "dosage", "smnn_code"])


def _empty_smnn_df() -> pd.DataFrame:
    return pd.DataFrame(columns=SMNN_COLUMNS)