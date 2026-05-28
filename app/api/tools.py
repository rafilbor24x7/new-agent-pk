from functools import lru_cache
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.services.base_store import get_base_dataframe, upload_base_file
from app.services.esklp_lookup import EsklpLookup
from app.services.excel_builder import build_result_workbook_bytes
from app.services.llm_client import DeepSeekLLMClient
from app.services.parser_offer import extract_offer_skus, parse_offer_text, read_offer_excel
from app.services.pk_list import load_pk_list
from app.services.pk_matcher import MatchPKInput, match_pk as match_pk_sku
from app.services.result_store import get_result_file, store_result_file

router = APIRouter(prefix="/tools", tags=["tools"])


class BuildExcelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_file_id: str = Field(min_length=1, description="file_id, полученный из /tools/upload_base")
    matched_skus: list[dict[str, Any]] = Field(default_factory=list)


class SearchEsklpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trade_name: str = Field(min_length=1, description="Торговое наименование SKU из КП")


@lru_cache(maxsize=1)
def get_esklp_lookup() -> EsklpLookup:
    return EsklpLookup()


@lru_cache(maxsize=1)
def get_llm_client() -> DeepSeekLLMClient:
    return DeepSeekLLMClient()


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


@router.post(
    "/match_pk",
    description="Подбирает товарную подкатегорию ПК по SKU, МНН, форме, дозировке, АТХ и ФТГ; при низкой уверенности использует LLM.",
)
def match_pk_tool(request: MatchPKInput) -> dict[str, Any]:
    return match_pk_sku(request.model_dump(), load_pk_list(), llm_client=get_llm_client())


@router.post(
    "/upload_base",
    description="Загружает основную Excel-выгрузку, проверяет обязательные колонки и сохраняет файл в памяти сессии.",
)
async def upload_base(file: UploadFile = File(...)) -> dict[str, Any]:
    content = await file.read()
    stored = upload_base_file(content, filename=file.filename)
    return {
        "file_id": stored.file_id,
        "rows": int(len(stored.dataframe)),
        "columns_ok": stored.columns_ok,
        "missing_columns": stored.missing_columns,
    }


@router.post(
    "/build_excel",
    description="Собирает итоговый Excel по основной выгрузке и списку сопоставленных SKU; возвращает ссылку на скачивание.",
)
def build_excel(request: BuildExcelRequest) -> dict[str, str]:
    try:
        base_df = get_base_dataframe(request.base_file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="base_file_id not found") from exc

    content = build_result_workbook_bytes(
        base_df,
        request.matched_skus,
        session_id=request.base_file_id,
    )
    stored = store_result_file(content)
    return {"download_url": f"/tools/download/{stored.file_id}"}


@router.get(
    "/download/{file_id}",
    description="Скачивает Excel-файл, собранный инструментом /tools/build_excel.",
)
def download_result(file_id: str) -> Response:
    try:
        stored = get_result_file(file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="file_id not found") from exc

    headers = {"Content-Disposition": f'attachment; filename="{stored.filename}"'}
    return Response(content=stored.content, media_type=stored.media_type, headers=headers)


def _optional_form_value(value: Any) -> str | None:
    if value is None or hasattr(value, "read"):
        return None
    text = str(value).strip()
    return text or None