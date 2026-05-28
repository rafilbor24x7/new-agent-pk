from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass
class StoredResultFile:
    file_id: str
    filename: str
    content: bytes
    media_type: str


_RESULT_FILES: dict[str, StoredResultFile] = {}


def store_result_file(
    content: bytes,
    filename: str | None = None,
    media_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
) -> StoredResultFile:
    file_id = uuid4().hex
    stored = StoredResultFile(
        file_id=file_id,
        filename=filename or f"result_{file_id}.xlsx",
        content=content,
        media_type=media_type,
    )
    _RESULT_FILES[file_id] = stored
    return stored


def get_result_file(file_id: str) -> StoredResultFile:
    stored = _RESULT_FILES.get(file_id)
    if stored is None:
        raise KeyError(file_id)
    return stored


def clear_result_files() -> None:
    _RESULT_FILES.clear()