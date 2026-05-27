from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


PK_LIST_PATH = Path("data/pk_list.json")


class PKItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tg: str = Field(min_length=1)
    tk: str = Field(min_length=1)
    pk: str = Field(min_length=1)


@lru_cache(maxsize=1)
def load_pk_list(path: str | Path = PK_LIST_PATH) -> list[dict[str, str]]:
    pk_path = Path(path)
    with pk_path.open("r", encoding="utf-8") as file:
        raw_items = json.load(file)

    return [PKItem.model_validate(item).model_dump() for item in raw_items]