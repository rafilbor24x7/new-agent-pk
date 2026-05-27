from pydantic import BaseModel, ConfigDict, Field


class SKUItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku_name_raw: str
    mnn: str | None = None
    dosage: str | None = None
    form: str | None = None
    pack_size: str | None = None
    zc: float | int | None = None
    rc: float | int | None = None
    sip: float | int | None = None
    bonus_percent: float | int | None = None
    vat_included: bool | None = None
    producer: str | None = None
    concern: str | None = None
    mnn_status: str = "mnn_unclear"
    is_duplicate: bool = False
    clarification_needed: list[str] = Field(default_factory=list)
    clarification_questions: list[str] = Field(default_factory=list)
    notes: str | None = None


class ParsedOfferResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skus: list[SKUItem]
    parser_notes: str | None = None
