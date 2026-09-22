from pydantic import BaseModel, Field


class _ScheduleInputs(BaseModel):
    principal: float = Field(gt=0)
    annual_rate: float = Field(ge=0)
    months: int = Field(gt=0, le=600)
    loan_id: int | None = None
    preview_rows: int = Field(default=12, ge=1, le=120)


class ScheduleRequest(_ScheduleInputs):
    persist: bool = True
    receipt_code: str | None = None


class PrecheckRequest(_ScheduleInputs):
    pass
