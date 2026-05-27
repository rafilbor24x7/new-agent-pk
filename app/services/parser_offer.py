from io import BytesIO
import re

import pandas as pd

from app.models.sku import ParsedOfferResult, SKUItem
from app.services.normalizer import normalize as normalize_text


SYSTEM_PROMPT = """Ты — специализированный парсер коммерческих предложений для аптечной сети.
Твоя задача — извлечь из текста список товарных позиций (SKU) и их коммерческие параметры.

Правила:
- Верни строго JSON без markdown-обёртки и пояснений.
- Не рассчитывай производные показатели.
- Не угадывай отсутствующие поля. Заполняй только явно извлечённые данные.
- Не отбрасывай непонятные позиции: включай их и добавляй clarification_questions.
- Если цена зависит от объёма, запиши минимальную цену в zc, условие в notes и вопрос пользователю.
- Если НДС не указан, vat_included=null и нужен вопрос про НДС.
- Если позиция повторяется с одинаковыми параметрами, включи один раз и поставь is_duplicate=true.

Поля SKU:
sku_name_raw, mnn, dosage, form, pack_size, zc, rc, sip, bonus_percent,
vat_included, producer, mnn_status, is_duplicate, clarification_needed,
clarification_questions, notes.
"""

USER_PROMPT_TEMPLATE = """Производитель: {producer}

Текст КП:
{text}

Верни строго JSON без markdown-обёртки, без пояснений. Формат:
{{
  "skus": [
    {{
      "sku_name_raw": "...",
      "mnn": "..." или null,
      "dosage": "..." или null,
      "form": "..." или null,
      "pack_size": "..." или null,
      "zc": число или null,
      "rc": число или null,
      "sip": число или null,
      "bonus_percent": число или null,
      "vat_included": true/false/null,
      "producer": "..." или null,
      "mnn_status": "mnn_extracted"|"mnn_suggested"|"mnn_unclear"|"mnn_not_required",
      "is_duplicate": true/false,
      "clarification_needed": ["zc", "vat_included"] или [],
      "clarification_questions": ["вопрос 1", "вопрос 2"] или [],
      "notes": "..." или null
    }}
  ],
  "parser_notes": "общие замечания по всему тексту или null"
}}
"""


def read_offer_excel(content: bytes) -> pd.DataFrame:
    df = pd.read_excel(BytesIO(content))
    return _promote_embedded_header(df)


def extract_offer_skus(df: pd.DataFrame) -> list[dict[str, object]]:
    df = _promote_embedded_header(df)
    if df.empty:
        return []

    name_column = _find_column(df.columns, ("полное наименование", "наименование", "товар"))
    if name_column is None:
        name_column = df.columns[0]

    mnn_column = _find_column(df.columns, ("мnn", "мнн", "действующее вещество"))
    concern_column = _find_column(df.columns, ("концерн", "производитель", "произоводитель"))
    zc_column = _find_column(df.columns, ("закупочная цена", "отгрузочная цена"))
    rc_column = _find_column(df.columns, ("ррц", "полочная цена"))
    sip_column = _find_column(df.columns, ("сип",))
    bonus_percent_column = _find_percent_column(df.columns, ("бонус", "скидка"))

    skus: list[dict[str, object]] = []

    for _, row in df.iterrows():
        raw_name = row.get(name_column)
        if pd.isna(raw_name):
            continue

        sku_name_raw = str(raw_name).strip()
        if not sku_name_raw or _is_header_label(sku_name_raw):
            continue

        mnn = _clean_text(row.get(mnn_column)) if mnn_column is not None else None
        skus.append(
            {
                "sku_name_raw": sku_name_raw,
                "mnn": mnn,
                "mnn_status": "mnn_extracted" if mnn else "mnn_unclear",
                "zc": _clean_number(row.get(zc_column)) if zc_column is not None else None,
                "rc": _clean_number(row.get(rc_column)) if rc_column is not None else None,
                "sip": _clean_number(row.get(sip_column)) if sip_column is not None else None,
                "bonus_percent": (
                    _clean_number(row.get(bonus_percent_column))
                    if bonus_percent_column is not None
                    else None
                ),
                "dosage": _extract_dosage(sku_name_raw),
                "form": _extract_form(sku_name_raw),
                "concern": _clean_text(row.get(concern_column)) if concern_column is not None else None,
            }
        )

    return skus


def _promote_embedded_header(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    first_row = df.iloc[0]
    first_row_labels = [_clean_text(value) for value in first_row.tolist()]
    if not any(label and _is_known_header(label) for label in first_row_labels):
        return df

    current_columns_have_names = any(_is_known_header(str(column)) for column in df.columns)
    if current_columns_have_names:
        return df

    promoted = df.iloc[1:].copy()
    promoted.columns = [
        label if label else f"column_{index}"
        for index, label in enumerate(first_row_labels)
    ]
    return promoted.reset_index(drop=True)


def _find_column(columns: pd.Index, markers: tuple[str, ...]) -> object | None:
    normalized_markers = tuple(marker.casefold() for marker in markers)
    for column in columns:
        normalized_column = str(column).strip().casefold()
        if any(marker in normalized_column for marker in normalized_markers):
            return column
    return None


def _find_percent_column(columns: pd.Index, markers: tuple[str, ...]) -> object | None:
    for column in columns:
        normalized_column = str(column).strip().casefold()
        if "%" not in normalized_column and "процент" not in normalized_column:
            continue
        if any(marker in normalized_column for marker in markers):
            return column
    return None


def _is_known_header(value: str) -> bool:
    normalized = value.strip().casefold()
    return any(
        marker in normalized
        for marker in (
            "полное наименование",
            "наименование",
            "товар",
            "мнн",
            "действующее вещество",
            "закупочная цена",
        )
    )


def _is_header_label(value: str) -> bool:
    return value.strip().casefold() in {"наименование", "полное наименование", "товар"}


def _clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _clean_number(value: object) -> float | int | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, int | float):
        return int(value) if float(value).is_integer() else float(value)

    text = str(value).strip().replace(" ", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None

    number = float(match.group(0))
    return int(number) if number.is_integer() else number


FIELD_PREFIXES = ("МНН", "ММН", "ЗЦ", "РЦ", "СИП", "Бонус", "бонус", "Бэк", "бэк")


def parse_plain_text(text: str, producer: str | None = None) -> ParsedOfferResult:
    skus = [
        _parse_text_sku(part, producer=producer)
        for part in _split_text_sku_parts(text)
        if part.strip()
    ]
    return ParsedOfferResult(skus=_deduplicate_skus(skus), parser_notes=None)


def parse_offer_text(text: str, producer: str | None = None) -> list[dict[str, object]]:
    return [sku.model_dump() for sku in parse_plain_text(text, producer=producer).skus]


def _split_text_sku_parts(text: str) -> list[str]:
    parts: list[str] = []
    blocks = [block.strip() for block in re.split(r"(?m)^\s*\d+[.)]\s*", text) if block.strip()]
    if len(blocks) <= 1:
        blocks = [text]

    for block in blocks:
        parts.extend(_split_block_sku_parts(block))

    return parts


def _split_block_sku_parts(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []

    for segment in [item.strip() for item in text.split(",")]:
        if not segment:
            continue

        starts_field = segment.startswith(FIELD_PREFIXES) or ":" in segment.split(" ", 1)[0]
        continues_current = _continues_same_position(segment, current)
        if current and not starts_field and not continues_current:
            parts.append(", ".join(current))
            current = [segment]
        else:
            current.append(segment)

    if current:
        parts.append(", ".join(current))

    return parts


def _continues_same_position(segment: str, current: list[str]) -> bool:
    if re.match(r"^(?:капс\.?|капсулы|табл\.?|таблетки|№|N)\b", segment, flags=re.IGNORECASE):
        return True

    current_text = " ".join(current)
    if re.search(r"\bсвыше\s*\d+\s*уп\b", current_text, flags=re.IGNORECASE):
        return True
    return bool(re.search(r"\b(?:цена будет|если объем|если объём|меньше|менее)\b", segment, flags=re.IGNORECASE))


def _parse_text_sku(part: str, producer: str | None = None) -> SKUItem:
    sku_name_raw = _extract_sku_name(part)
    clarification_needed: list[str] = []
    clarification_questions: list[str] = []
    volume_price = _extract_volume_price(part)
    zc = volume_price["zc"] if volume_price else _extract_price(part, ("ЗЦ", "закупке", "закупочная цена", "цена в закупке"))
    rc = _extract_price(part, ("РЦ",))
    sip = _extract_price(part, ("СИП",))
    bonus_percent = _extract_bonus_percent(part)
    vat_included = _extract_vat(part)
    mnn, mnn_status, mnn_note = _extract_mnn(part)

    generic_price = _extract_generic_price(part)
    if volume_price:
        clarification_needed.append("zc")
        clarification_questions.append(str(volume_price["question"]))
    elif zc is None and generic_price is not None:
        zc = generic_price
        clarification_needed.append("zc")
        clarification_questions.append(f"Уточните: {generic_price:g} рублей — это закупочная цена (ЗЦ)?")

    if (zc is not None or rc is not None or sip is not None) and vat_included is None:
        clarification_needed.append("vat_included")
        if rc is not None:
            clarification_questions.append(f"Цены (ЗЦ {zc:g}, РЦ {rc:g}) указаны с НДС или без?")
        else:
            clarification_questions.append(f"Цена {zc:g} руб указана с НДС или без?")

    return SKUItem(
        sku_name_raw=sku_name_raw,
        mnn=mnn,
        dosage=_extract_dosage(sku_name_raw),
        form=_extract_form(sku_name_raw),
        pack_size=_extract_pack_size(sku_name_raw),
        zc=_normalize_number(zc),
        rc=_normalize_number(rc),
        sip=_normalize_number(sip),
        bonus_percent=_normalize_number(bonus_percent),
        vat_included=vat_included,
        producer=producer.strip() if producer and producer.strip() else None,
        concern=producer.strip() if producer and producer.strip() else None,
        mnn_status=mnn_status,
        is_duplicate=False,
        clarification_needed=clarification_needed,
        clarification_questions=clarification_questions,
        notes=_join_notes(mnn_note, str(volume_price["notes"]) if volume_price else None),
    )


def _deduplicate_skus(skus: list[SKUItem]) -> list[SKUItem]:
    unique_skus: list[SKUItem] = []
    seen_by_key: dict[tuple[object, ...], SKUItem] = {}

    for sku in skus:
        key = _duplicate_key(sku)
        existing = seen_by_key.get(key)
        if existing is None:
            seen_by_key[key] = sku
            unique_skus.append(sku)
            continue

        existing.is_duplicate = True
        if "duplicate" not in existing.clarification_needed:
            existing.clarification_needed.append("duplicate")
        question = f"Позиция '{existing.sku_name_raw}' встречается дважды с одинаковыми параметрами. Оставить одну?"
        if question not in existing.clarification_questions:
            existing.clarification_questions.append(question)

    return unique_skus


def _duplicate_key(sku: SKUItem) -> tuple[object, ...]:
    return (
        normalize_text(sku.sku_name_raw),
        normalize_text(sku.mnn),
        sku.dosage,
        sku.pack_size,
        sku.zc,
        sku.rc,
        sku.sip,
        sku.bonus_percent,
        sku.vat_included,
    )


def _extract_sku_name(text: str) -> str:
    introduced = re.search(
        r"(?:новую позицию|позицию|товар)\s*-\s*([^.\n]+)",
        text,
        flags=re.IGNORECASE,
    )
    if introduced:
        return introduced.group(1).strip(" .,-")

    name = re.split(
        r"\s+-\s+|[,.]\s*(?:МНН|ММН|ЗЦ|РЦ|СИП|Бонус|бонус|Бэк|бэк|Цена|цена)\b|\s+(?:ЗЦ|РЦ|СИП|Цена|цена)\b",
        text,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    name = re.sub(r"\((?:МНН|ММН|действующее вещество) [^)]+\)", "", name, flags=re.IGNORECASE)
    return name.strip(" .,-")


def _extract_mnn(text: str) -> tuple[str | None, str, str | None]:
    match = re.search(
        r"(?:МНН|ММН|действующее вещество)\s*:?\s*([А-Яа-яA-Za-zёЁ -]+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None, "mnn_unclear", None

    mnn = re.split(r"[).,;]", match.group(1), maxsplit=1)[0].strip()
    note = "В тексте 'ММН' — распознано как МНН" if re.search(r"\bММН\b", text, re.IGNORECASE) else None
    return mnn or None, "mnn_extracted", note


def _extract_price(text: str, labels: tuple[str, ...]) -> float | None:
    for label in labels:
        match = re.search(
            rf"{re.escape(label)}[^0-9]{{0,30}}([0-9]+(?:[.,][0-9]+)?)",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            return float(match.group(1).replace(",", "."))
    return None


def _extract_generic_price(text: str) -> float | None:
    if re.search(r"\b(?:ЗЦ|РЦ|СИП)\b", text, flags=re.IGNORECASE):
        return None

    match = re.search(
        r"(?:цена|цене|стоимость)[^0-9]{0,30}([0-9]+(?:[.,][0-9]+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return float(match.group(1).replace(",", "."))

    return None


def _extract_volume_price(text: str) -> dict[str, object] | None:
    match = re.search(
        r"свыше\s*(?P<threshold>\d+)\s*уп[^0-9]+(?P<high>[0-9]+(?:[.,][0-9]+)?).*?"
        r"(?:меньше|менее)[^0-9]+(?P<low>[0-9]+(?:[.,][0-9]+)?)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return None

    threshold = int(match.group("threshold"))
    high_volume_price = float(match.group("high").replace(",", "."))
    low_volume_price = float(match.group("low").replace(",", "."))
    zc = min(high_volume_price, low_volume_price)

    return {
        "zc": zc,
        "question": (
            f"Цена зависит от объёма: {high_volume_price:g} руб (от {threshold} уп) "
            f"или {low_volume_price:g} руб (менее {threshold} уп). Какую использовать?"
        ),
        "notes": (
            f"При закупке свыше {threshold} уп — {high_volume_price:g} руб, "
            f"менее {threshold} уп — {low_volume_price:g} руб"
        ),
    }


def _extract_bonus_percent(text: str) -> float | None:
    match = re.search(r"(?:Бэк|бэк|Бонус|бонус)[^0-9]{0,20}([0-9]+(?:[.,][0-9]+)?)\s*%", text)
    if match:
        return float(match.group(1).replace(",", "."))
    return None


def _extract_vat(text: str) -> bool | None:
    if re.search(r"без\s+НДС", text, flags=re.IGNORECASE):
        return False
    if re.search(r"с\s+НДС", text, flags=re.IGNORECASE):
        return True
    return None


def _extract_dosage(text: str) -> str | None:
    match = re.search(r"\b\d+(?:[.,]\d+)?\s*(?:мг|mg|мл|ml|г|g)\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _extract_form(text: str) -> str | None:
    match = re.search(
        r"\b(готовое полоскание|капс\.?|табл\.?|таблетки|капсулы|сироп|раствор|спрей|полоскание)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    form = match.group(0)
    if form.lower().startswith("капс"):
        return "капсулы"
    return form


def _extract_pack_size(text: str) -> str | None:
    match = re.search(r"(?:№|N)\s*\d+", text, flags=re.IGNORECASE)
    return match.group(0).replace("N", "№") if match else None


def _normalize_number(value: float | None) -> float | int | None:
    if value is None:
        return None
    return int(value) if value.is_integer() else value


def _join_notes(*notes: str | None) -> str | None:
    cleaned_notes = [note for note in notes if note]
    return "; ".join(cleaned_notes) if cleaned_notes else None
