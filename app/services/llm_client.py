from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class MatchPKLLMResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pk: str = Field(min_length=1)
    tg: str | None = None
    tk: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1)
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class DeepSeekLLMClient:
    def __init__(self, api_key: str | None = None, model: str = "deepseek-chat") -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model
        self._client = OpenAI(api_key=self.api_key, base_url="https://api.deepseek.com") if self.api_key else None

    def can_match_pk(self) -> bool:
        return self._client is not None

    def match_pk(
        self,
        sku: dict[str, Any],
        pk_list: list[dict[str, str]],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")

        prompt = {
            "task": "Выбери одну товарную подкатегорию ПК для SKU. Используй МНН, форму, дозировку, АТХ-код, АТХ-наименование и ФТГ, если они есть. Ответ строго JSON.",
            "sku": sku,
            "pk_list": pk_list,
            "fuzzy_candidates": candidates,
            "schema": {"pk": "...", "tg": "...", "tk": "...", "confidence": 0.0, "reason": "..."},
        }
        for _ in range(3):
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты классификатор аптечных SKU по списку ПК. Учитывай АТХ и ФТГ для различения областей применения. Отвечай только JSON."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
            try:
                return MatchPKLLMResponse.model_validate_json(content).model_dump()
            except ValidationError:
                continue
        raise ValueError("DeepSeek returned invalid match_pk JSON three times")