from functools import lru_cache
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.services.esklp_lookup import EsklpLookup
from app.services.pk_list import load_pk_list

router = APIRouter(prefix="/tools", tags=["tools"])


class SearchEsklpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_name: str = Field(min_length=1, description="Торговое наименование SKU из КП")


@lru_cache(maxsize=1)
def get_esklp_lookup() -> EsklpLookup:
    return EsklpLookup()


@router.get(
    "/pk_list",
    description="Возвращает полный статичный список товарных подкатегорий ПК для выбора агентом.",
)
def get_pk_list() -> list[dict[str, str]]:
    return load_pk_list()


@router.post(
    "/search_esklp",
    description="Ищет МНН, лекарственную форму и дозировку в ЕСКЛП по торговому наименованию SKU.",
)
def search_esklp(request: SearchEsklpRequest) -> list[dict[str, Any]]:
    return get_esklp_lookup().search(request.trade_name)