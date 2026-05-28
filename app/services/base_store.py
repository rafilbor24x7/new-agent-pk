from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from uuid import uuid4

import pandas as pd


REQUIRED_BASE_COLUMNS = {
    "ТГ",
    "ТК",
    "ПК",
    "МНН",
    "Концерн",
    "Номенклатура",
    "РЦ",
    "ЗЦ",
}


@dataclass
class StoredBaseFile:
    file_id: str
    filename: str | None
    dataframe: pd.DataFrame
    missing_columns: list[str]

    @property
    def columns_ok(self) -> bool:
        return not self.missing_columns


_BASE_FILES: dict[str, StoredBaseFile] = {}


def upload_base_file(content: bytes, filename: str | None = None) -> StoredBaseFile:
    dataframe = pd.read_excel(BytesIO(content))
    missing_columns = sorted(REQUIRED_BASE_COLUMNS.difference(map(str, dataframe.columns)))
    file_id = uuid4().hex
    stored = StoredBaseFile(
        file_id=file_id,
        filename=filename,
        dataframe=dataframe,
        missing_columns=missing_columns,
    )
    _BASE_FILES[file_id] = stored
    return stored


def get_base_dataframe(file_id: str) -> pd.DataFrame:
    stored = _BASE_FILES.get(file_id)
    if stored is None:
        raise KeyError(file_id)
    return stored.dataframe.copy()


def clear_base_files() -> None:
    _BASE_FILES.clear()