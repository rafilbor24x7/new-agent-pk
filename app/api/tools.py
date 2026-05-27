from fastapi import APIRouter

from app.services.pk_list import load_pk_list

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get(
    "/pk_list",
    description="Возвращает полный статичный список товарных подкатегорий ПК для выбора агентом.",
)
def get_pk_list() -> list[dict[str, str]]:
    return load_pk_list()