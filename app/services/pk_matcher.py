from __future__ import annotations

import re
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field
from rapidfuzz import fuzz, process


CONFIDENCE_AUTO = 0.90
CONFIDENCE_REVIEW = 0.65


class MatchPKInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trade_name: str = Field(default="")
    mnn: str | None = None
    form: str | None = None
    dosage: str | None = None
    atx_code: str | None = None
    atx_name: str | None = None
    ftg_name: str | None = None


class PKLLMClient(Protocol):
    def can_match_pk(self) -> bool: ...

    def match_pk(
        self,
        sku: dict[str, Any],
        pk_list: list[dict[str, str]],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]: ...


def match_pk(
    sku_payload: dict[str, Any],
    pk_list: list[dict[str, str]],
    llm_client: PKLLMClient | None = None,
) -> dict[str, Any]:
    sku = MatchPKInput.model_validate(sku_payload)
    candidates = _build_candidates(sku, pk_list)
    best = candidates[0] if candidates else None

    if best and best["confidence"] >= CONFIDENCE_AUTO:
        return _result_from_candidate(best, "auto_matched", "fuzzy_pk_match")

    if llm_client is not None and llm_client.can_match_pk():
        llm_result = llm_client.match_pk(sku.model_dump(), pk_list, candidates)
        return _result_from_llm(llm_result, candidates)

    if best and best["confidence"] >= CONFIDENCE_REVIEW:
        return _result_from_candidate(best, "review_required", "fuzzy_candidates_need_review")

    return {
        "pk": None,
        "tg": None,
        "tk": None,
        "confidence": best["confidence"] if best else 0.0,
        "status": "need_clarification",
        "reason": "llm_unavailable_or_low_confidence",
        "candidates": candidates[:3],
    }


def _build_candidates(sku: MatchPKInput, pk_list: list[dict[str, str]]) -> list[dict[str, Any]]:
    query = _build_query(sku)
    if not query:
        query = sku.trade_name
    choices = [_item_text(item) for item in pk_list]
    matches = process.extract(query, choices, scorer=fuzz.WRatio, limit=5)

    candidates: list[dict[str, Any]] = []
    for _, score, index in matches:
        item = pk_list[index]
        confidence = round(float(score) / 100, 2)
        if _query_contains_pk(query, item["pk"]):
            confidence = 1.0
        candidates.append(
            {
                "tg": item["tg"],
                "tk": item["tk"],
                "pk": item["pk"],
                "confidence": confidence,
                "reason": "fuzzy_pk_candidate",
            }
        )
    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    return candidates


def _build_query(sku: MatchPKInput) -> str:
    parts = [
        sku.mnn,
        sku.trade_name,
        sku.form,
        sku.dosage,
        sku.atx_code,
        sku.atx_name,
        sku.ftg_name,
    ]
    return " ".join(str(part).strip() for part in parts if part).strip()


def _item_text(item: dict[str, str]) -> str:
    return " ".join([item["tg"], item["tk"], item["pk"]])


def _query_contains_pk(query: str, pk: str) -> bool:
    query_tokens = set(_tokens(query))
    pk_tokens = [token for token in _tokens(pk) if len(token) > 1]
    return bool(pk_tokens and all(token in query_tokens for token in pk_tokens))


def _tokens(value: str) -> list[str]:
    return re.findall(r"[0-9a-zа-яё]+", value.casefold())


def _result_from_candidate(candidate: dict[str, Any], status: str, reason: str) -> dict[str, Any]:
    return {
        "pk": candidate["pk"] if status == "auto_matched" else None,
        "tg": candidate["tg"] if status == "auto_matched" else None,
        "tk": candidate["tk"] if status == "auto_matched" else None,
        "confidence": candidate["confidence"],
        "status": status,
        "reason": reason,
        "candidates": [candidate],
    }


def _result_from_llm(llm_result: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    confidence = float(llm_result.get("confidence") or 0.0)
    status = "auto_matched" if confidence >= CONFIDENCE_AUTO else "review_required"
    pk = str(llm_result.get("pk") or "").strip() or None
    tg = str(llm_result.get("tg") or "").strip() or None
    tk = str(llm_result.get("tk") or "").strip() or None
    return {
        "pk": pk if status == "auto_matched" else None,
        "tg": tg if status == "auto_matched" else None,
        "tk": tk if status == "auto_matched" else None,
        "confidence": confidence,
        "status": status,
        "reason": str(llm_result.get("reason") or "llm_match"),
        "candidates": llm_result.get("candidates") or candidates[:3],
    }