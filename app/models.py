from typing import Optional, List, Literal
from pydantic import BaseModel, Field, validator, model_validator

# --- Входные модели --- #

class IncomeSchema(BaseModel):
    source: str = Field(..., description="Источник дохода (например, salary, business, rent)")
    amount: float = Field(..., gt=0, description="Размер дохода")
    currency: str = Field(..., min_length=3, max_length=3, description="Валюта (ISO код, например, RUB, USD, EUR)")

class ObligationSchema(BaseModel):
    type: str
    monthly_payment: Optional[float] = None
    balance: Optional[float] = None
    min_payment_rate: Optional[float] = None

    @model_validator(mode="after")
    def validate_payment_combo(self):
        has_payment = self.monthly_payment is not None and self.monthly_payment > 0
        has_balance_rate = (
            self.balance is not None
            and self.min_payment_rate is not None
            and self.min_payment_rate > 0
        )

        if not (has_payment or has_balance_rate):
            raise ValueError(
                "Должен быть указан либо monthly_payment > 0, либо balance и min_payment_rate"
            )
        return self


class ScenarioSchema(BaseModel):
    mode: Literal["base", "stress"] = Field(..., description="Режим расчёта (base или stress)")
    shock: Optional[float] = Field(0.0, ge=-0.5, le=1.0, description="Шок для стресс-сценария (-0.5 … +1.0)")


class AssumptionsSchema(BaseModel):
    pdn_limit: float = Field(0.5, ge=0, le=1, description="Предельный уровень ПДН (по умолчанию 50%)")
    stress_factor: float = Field(1.3, ge=1.0, le=2.0, description="Множитель для стресс-сценария")


class MetaSchema(BaseModel):
    ts: Optional[str] = Field(None, description="Timestamp запроса (опционально)")
    calc_version: str = Field("0.1.0", description="Версия расчёта")
    risk_band: Optional[str] = Field(None, description="Риск-категория (опционально)")


class PDNRequestSchema(BaseModel):
    subject_type: Literal["individual", "organization"] = "individual"
    incomes: List[IncomeSchema]
    obligations: List[ObligationSchema]
    scenario: ScenarioSchema
    assumptions: Optional[AssumptionsSchema] = None
    meta: Optional[MetaSchema] = None

# --- Выходная модель --- #

class CalcResultSchema(BaseModel):
    pdn_ratio: float = Field(..., ge=0, le=1, description="Рассчитанный коэффициент ПДН (Debt-to-Income)")
    status: Literal["ok", "warning", "error"]
    breakdown: dict = Field(..., description="Расшифровка расчёта по доходам и обязательствам")
    meta: MetaSchema
