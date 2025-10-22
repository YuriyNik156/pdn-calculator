from typing import Optional, List, Literal, Union
from pydantic import BaseModel, Field, validator, model_validator


# --- Входные модели --- #

class IncomeSchema(BaseModel):
    amount: float = Field(..., gt=0, description="Размер дохода")
    currency: str = Field(..., min_length=3, max_length=3, description="Валюта (ISO код, например, RUB, USD, EUR)")
    income_type: Literal["net", "gross"] = Field("net", description="Тип дохода: net или gross")
    source: str = Field(..., description="Источник дохода (например, payroll, business, rent)")


class ObligationSchema(BaseModel):
    type: Literal["loan", "credit_card", "alimony", "installment", "other"]
    monthly_payment: Optional[float] = Field(None, ge=0, description="Ежемесячный платёж (если известен)")
    balance: Optional[float] = Field(None, ge=0, description="Баланс (для кредитных карт)")
    min_payment_rate: Optional[float] = Field(None, ge=0, le=1, description="Минимальный платёж в % для карт")
    currency: Optional[str] = Field("RUB", min_length=3, max_length=3, description="Валюта")
    name: Optional[str] = Field(None, description="Название обязательства (например, Ипотека)")


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


class RefinanceSchema(BaseModel):
    monthly_payment: Optional[float] = Field(None, ge=0)
    balance: Optional[float] = Field(None, ge=0)
    min_payment_rate: Optional[float] = Field(None, ge=0, le=1)
    name: Optional[str] = None


class ScenarioSchema(BaseModel):
    mode: Literal["base", "stress", "target"] = Field(..., description="Режим расчёта")
    income_shock_pct: Optional[float] = Field(0.0, ge=-1.0, le=1.0, description="Шок дохода (-100% … +100%)")
    payment_shock_pct: Optional[float] = Field(0.0, ge=-1.0, le=1.0, description="Шок платежей (-100% … +100%)")
    refinance: Optional[RefinanceSchema] = None


class AssumptionsSchema(BaseModel):
    credit_card_default_min_rate: float = Field(0.05, ge=0, le=1, description="Минимальная ставка по кредитной карте")
    rounding: int = Field(2, ge=0, description="Округление денежных значений и процентов")


class MetaSchema(BaseModel):
    client_id: Optional[str] = Field(None, description="ID клиента")
    request_id: Optional[str] = Field(None, description="UUID запроса")
    ts: Optional[str] = Field(None, description="Timestamp запроса")


class PDNRequestSchema(BaseModel):
    subject_type: Literal["individual", "business"] = "individual"
    period_months: Optional[int] = Field(6, ge=1, description="Период дохода в месяцах")
    income: IncomeSchema
    obligations: List[ObligationSchema]
    scenario: ScenarioSchema
    assumptions: Optional[AssumptionsSchema] = None
    meta: Optional[MetaSchema] = None


# --- Выходная модель --- #

class BreakdownItemSchema(BaseModel):
    name: str
    monthly: float


class CalcResultSchema(BaseModel):
    calc_version: str
    currency: str
    monthly_obligations_total: float
    monthly_income_used: float
    pdn_percent: float
    risk_band: Literal["LOW", "MID", "HIGH"]
    breakdown: List[BreakdownItemSchema]
    scenario_applied: str
    advice: Optional[str] = None
    meta: MetaSchema
