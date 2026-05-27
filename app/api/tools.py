from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.esklp_lookup import EsklpLookup
from app.services.parser_offer import extract_offer_skus, parse_offer_text, read_offer_excel
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


@router.post(
    "/parse_offer",
    description="Парсит коммерческое предложение из текста или Excel-файла и возвращает список SKU.",
)
async def parse_offer(request: Request) -> list[dict[str, Any]]:
    content_type = request.headers.get("content-type", "").casefold()

    if "multipart/form-data" in content_type:
        form = await request.form()
        producer = _optional_form_value(form.get("producer"))
        file = form.get("file")
        text = _optional_form_value(form.get("text"))
        if file is not None and hasattr(file, "read"):
            content = await file.read()
            return extract_offer_skus(read_offer_excel(content))
        if text:
            return parse_offer_text(text, producer=producer)
        raise HTTPException(status_code=400, detail="Provide text or file")

    payload = await request.json()
    text = str(payload.get("text") or "").strip() if isinstance(payload, dict) else ""
    producer = str(payload.get("producer") or "").strip() if isinstance(payload, dict) else ""
    if not text:
        raise HTTPException(status_code=400, detail="Field text is required")
    return parse_offer_text(text, producer=producer or None)


def _optional_form_value(value: Any) -> str | None:
    if value is None or hasattr(value, "read"):
        return None
    text = str(value).strip()
    return text or None