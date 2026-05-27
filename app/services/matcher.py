from dataclasses import asdict, dataclass
from typing import Callable

import pandas as pd
from pydantic import BaseModel, Field

from app.services.normalizer import normalize


AUTO_MATCH_CONFIDENCE = 0.95
CONFIDENCE_AUTO = 0.90
CONFIDENCE_REVIEW = 0.65
STATUS_AUTO_MATCHED = "auto_matched"
STATUS_REVIEW_REQUIRED = "review_required"
STATUS_UNMATCHED = "unmatched"
SCORING_WEIGHTS = {
    "mnn": 0.50,
    "form": 0.20,
    "dosage": 0.15,
    "concern": 0.15,
}
LLMFallback = Callable[[dict[str, object], pd.DataFrame], dict[str, object]]


class LLMFallbackResponse(BaseModel):
    pk: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)


@dataclass(frozen=True)
class MatchResult:
    status: str
    confidence: float
    pk: str | None
    candidates: list[dict[str, object]]
    reason: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def match_exact_mnn(sku: dict[str, object], base_df: pd.DataFrame) -> MatchResult:
    sku_mnn = sku.get("mnn")
    if not sku_mnn:
        return _unmatched("mnn_missing")

    normalized_sku_mnn = normalize(sku_mnn)
    if not normalized_sku_mnn:
        return _unmatched("mnn_missing")

    matched_rows = base_df[
        base_df["МНН"].map(normalize) == normalized_sku_mnn
    ]
    if matched_rows.empty:
        return _unmatched("exact_mnn_not_found")

    pk = _most_frequent_non_empty(matched_rows["ПК"])
    if pk is None:
        return _unmatched("pk_missing")

    return MatchResult(
        status=STATUS_AUTO_MATCHED,
        confidence=AUTO_MATCH_CONFIDENCE,
        pk=pk,
        candidates=[_build_candidate(pk, matched_rows)],
        reason="exact_mnn_match",
    )


def match_by_scoring(sku: dict[str, object], base_df: pd.DataFrame) -> MatchResult:
    scored_candidates: list[tuple[float, pd.Series, list[str]]] = []

    for _, row in base_df.iterrows():
        score, matched_fields = score_sku_against_row(sku, row)
        if score > 0:
            scored_candidates.append((score, row, matched_fields))

    if not scored_candidates:
        return _unmatched("no_scoring_candidates")

    scored_candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_row, best_fields = scored_candidates[0]
    status = _status_from_confidence(best_score)

    if status == STATUS_UNMATCHED:
        return _unmatched("score_below_threshold")

    pk = _row_value(best_row, "ПК")
    candidates = [
        _build_scored_candidate(row, score, fields)
        for score, row, fields in scored_candidates[:3]
    ]

    return MatchResult(
        status=status,
        confidence=round(best_score, 2),
        pk=pk if status == STATUS_AUTO_MATCHED else None,
        candidates=candidates,
        reason="field_scoring",
    )


def match_with_llm_fallback(
    sku: dict[str, object],
    base_df: pd.DataFrame,
    llm_fallback: LLMFallback,
) -> MatchResult:
    scored_result = match_by_scoring(sku, base_df)
    if scored_result.status != STATUS_UNMATCHED:
        return scored_result

    fallback = LLMFallbackResponse.model_validate(llm_fallback(sku, base_df))
    status = _status_from_confidence(fallback.confidence)

    return MatchResult(
        status=status,
        confidence=fallback.confidence,
        pk=fallback.pk if status == STATUS_AUTO_MATCHED else None,
        candidates=[
            {
                "pk": fallback.pk,
                "confidence": fallback.confidence,
                "reason": fallback.reason,
            }
        ],
        reason=f"llm_fallback:{fallback.reason}",
    )


def group_skus_by_pk(matched_skus: list[dict[str, object]]) -> list[dict[str, object]]:
    groups_by_pk: dict[str, dict[str, object]] = {}

    for item in matched_skus:
        pk = _item_pk(item)
        if pk is None:
            continue

        group = groups_by_pk.setdefault(pk, {"pk": pk, "skus": []})
        group["skus"].append(item)

    return list(groups_by_pk.values())


def score_sku_against_row(
    sku: dict[str, object],
    row: pd.Series,
) -> tuple[float, list[str]]:
    score = 0.0
    matched_fields: list[str] = []
    base_name = _row_value(row, "Номенклатура")

    if _values_match(sku.get("mnn"), row.get("МНН")):
        score += SCORING_WEIGHTS["mnn"]
        matched_fields.append("mnn")

    if _value_in_text(sku.get("form"), base_name):
        score += SCORING_WEIGHTS["form"]
        matched_fields.append("form")

    if _value_in_text(sku.get("dosage"), base_name):
        score += SCORING_WEIGHTS["dosage"]
        matched_fields.append("dosage")

    if _values_match(sku.get("concern"), row.get("Концерн")):
        score += SCORING_WEIGHTS["concern"]
        matched_fields.append("concern")

    return round(score, 2), matched_fields


def _unmatched(reason: str) -> MatchResult:
    return MatchResult(
        status=STATUS_UNMATCHED,
        confidence=0.0,
        pk=None,
        candidates=[],
        reason=reason,
    )


def _most_frequent_non_empty(series: pd.Series) -> str | None:
    values = series.dropna().astype(str).str.strip()
    values = values[values != ""]
    if values.empty:
        return None
    return str(values.value_counts().index[0])


def _status_from_confidence(confidence: float) -> str:
    if confidence >= CONFIDENCE_AUTO:
        return STATUS_AUTO_MATCHED
    if confidence >= CONFIDENCE_REVIEW:
        return STATUS_REVIEW_REQUIRED
    return STATUS_UNMATCHED


def _build_candidate(pk: str, rows: pd.DataFrame) -> dict[str, object]:
    first_row = rows.iloc[0]
    return {
        "pk": pk,
        "tk": _row_value(first_row, "ТК"),
        "tg": _row_value(first_row, "ТГ"),
        "example_sku": _row_value(first_row, "Номенклатура"),
        "reason": "exact_mnn_match",
    }


def _build_scored_candidate(
    row: pd.Series,
    confidence: float,
    matched_fields: list[str],
) -> dict[str, object]:
    return {
        "pk": _row_value(row, "ПК"),
        "tk": _row_value(row, "ТК"),
        "tg": _row_value(row, "ТГ"),
        "example_sku": _row_value(row, "Номенклатура"),
        "confidence": round(confidence, 2),
        "matched_fields": matched_fields,
        "reason": "field_scoring",
    }


def _row_value(row: pd.Series, column: str) -> str | None:
    value = row.get(column)
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _values_match(left: object, right: object) -> bool:
    normalized_left = normalize(left)
    normalized_right = normalize(right)
    return bool(normalized_left and normalized_left == normalized_right)


def _value_in_text(value: object, text: object) -> bool:
    normalized_value = normalize(value)
    normalized_text = normalize(text)
    return bool(normalized_value and normalized_value in normalized_text.split())


def _item_pk(item: dict[str, object]) -> str | None:
    match = item.get("match")

    if isinstance(match, MatchResult):
        return match.pk

    if isinstance(match, dict):
        pk = match.get("pk")
        return str(pk).strip() if pk else None

    pk = item.get("pk")
    return str(pk).strip() if pk else None
