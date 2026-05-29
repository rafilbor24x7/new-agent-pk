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
TN_SOURCE_COLUMNS = {
    "trade_name": "Торговое наименование",
    "smnn_code": "Код узла СМНН",
    "mnn": "Стандартизованное МНН",
    "form": "Стандартизованная лекарственная форма",
    "dosage_value": "Стандартизованная дозировка кол-во",
    "dosage_unit": "Единица измерения",
    "dosage": "Список нормализованных лекарственных форм и дозировок",
}
SMNN_SOURCE_COLUMNS = {
    "smnn_code": "Код узла СМНН",
    "ftg_name": "Наименование ФТГ",
    "atx_code": "код АТХ",
    "atx_name": "Наименование",
}
TN_COLUMNS = ["trade_name", "mnn", "form", "dosage", "smnn_code"]
SMNN_COLUMNS = ["smnn_code", "atx_code", "atx_name", "ftg_name"]
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
        df = df.drop_duplicates(subset=TN_COLUMNS)
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
    raw = _read_esklp_excel(path)
    if raw.empty:
        return _empty_tn_df()

    _require_columns(path, raw, TN_SOURCE_COLUMNS.values())
    df = pd.DataFrame(
        {
            "trade_name": raw[TN_SOURCE_COLUMNS["trade_name"]],
            "mnn": raw[TN_SOURCE_COLUMNS["mnn"]],
            "form": raw[TN_SOURCE_COLUMNS["form"]],
            "dosage": raw[TN_SOURCE_COLUMNS["dosage"]],
            "smnn_code": raw[TN_SOURCE_COLUMNS["smnn_code"]],
        }
    )
    df["dosage"] = df["dosage"].where(
        df["dosage"].map(_clean_value).notna(),
        raw.apply(_join_dosage, axis=1),
    )
    return _clean_dataframe(df, TN_COLUMNS)


def _read_smnn_file(path: Path) -> pd.DataFrame:
    raw = _read_esklp_excel(path)
    if raw.empty:
        return _empty_smnn_df()

    _require_columns(path, raw, SMNN_SOURCE_COLUMNS.values())
    df = pd.DataFrame(
        {
            "smnn_code": raw[SMNN_SOURCE_COLUMNS["smnn_code"]],
            "atx_code": raw[SMNN_SOURCE_COLUMNS["atx_code"]],
            "atx_name": raw[SMNN_SOURCE_COLUMNS["atx_name"]],
            "ftg_name": raw[SMNN_SOURCE_COLUMNS["ftg_name"]],
        }
    )
    return _clean_dataframe(df, SMNN_COLUMNS)


def _read_esklp_excel(path: Path) -> pd.DataFrame:
    return pd.read_excel(path, dtype=str)


def _require_columns(path: Path, df: pd.DataFrame, columns: Any) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"{path.name}: missing columns: {missing_text}")


def _clean_dataframe(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in df.columns:
        df[column] = df[column].map(_clean_value)
    return df[columns]


def _join_dosage(row: pd.Series) -> str | None:
    value = _clean_value(row.get(TN_SOURCE_COLUMNS["dosage_value"]))
    unit = _clean_value(row.get(TN_SOURCE_COLUMNS["dosage_unit"]))
    if value and unit:
        return f"{value} {unit}"
    return value or unit


def _clean_value(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _empty_tn_df() -> pd.DataFrame:
    return pd.DataFrame(columns=TN_COLUMNS)


def _empty_smnn_df() -> pd.DataFrame:
    return pd.DataFrame(columns=SMNN_COLUMNS)
