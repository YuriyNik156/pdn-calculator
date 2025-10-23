from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from uuid import uuid4
from datetime import datetime


# --------------------------
# Схема дохода
# --------------------------
class IncomeSchema(BaseModel):
    amount: float
    currency: str = "RUB"
    income_type: Literal["net", "gross"] = "net"
    source: Literal["salary", "other"] = "salary"


# --------------------------
# Схема обязательств
# --------------------------
class ObligationSchema(BaseModel):
    type: Literal["loan", "credit_card", "alimony", "installment"]
    balance: Optional[float] = None
    monthly_payment: Optional[float] = None
    min_payment_rate: Optional[float] = None
    name: Optional[str] = None


# --------------------------
# Сценарии расчёта
# --------------------------
class ScenarioSchema(BaseModel):
    mode: Literal["base", "stress", "target"]
    income_shock_pct: float = 0
    payment_shock_pct: float = 0
    refinance: Optional[List[ObligationSchema]] = None


# --------------------------
# Допущения / Assumptions
# --------------------------
class AssumptionsSchema(BaseModel):
    credit_card_default_min_rate: float = 0.05
    rounding: int = 2


# --------------------------
# Метаданные
# --------------------------
class MetaSchema(BaseModel):
    client_id: str
    request_id: str = Field(default_factory=lambda: str(uuid4()))


# --------------------------
# Главная схема запроса (PDN физлицо)
# --------------------------
class PDNRequestSchema(BaseModel):
    subject_type: Literal["individual", "business"] = "individual"
    period_months: int = Field(6, ge=1)
    income: IncomeSchema
    obligations: List[ObligationSchema]
    scenario: ScenarioSchema
    assumptions: Optional[AssumptionsSchema] = AssumptionsSchema()
    meta: MetaSchema

    @validator("income")
    def validate_income(cls, v):
        if v.amount <= 0:
            raise ValueError("income.amount must be > 0")
        allowed_currencies = ["RUB", "USD", "EUR"]
        if v.currency not in allowed_currencies:
            raise ValueError(f"Unsupported currency {v.currency}")
        return v

    @validator("obligations")
    def validate_obligations(cls, v, values):
        total_payments = 0
        income_amount = values.get("income").amount if values.get("income") else 1
        assumptions = values.get("assumptions") or AssumptionsSchema()

        for obl in v:
            monthly = obl.monthly_payment
            if monthly is None:
                if obl.type == "credit_card":
                    rate = obl.min_payment_rate or assumptions.credit_card_default_min_rate
                    monthly = (obl.balance or 0) * rate
                else:
                    if obl.balance is None:
                        raise ValueError(f"Obligation {obl.name or obl.type} missing payment info")
                    monthly = obl.balance
            if monthly < 0:
                raise ValueError(f"Obligation {obl.name or obl.type} has negative payment")
            total_payments += monthly

        if total_payments > 0.9 * income_amount:
            raise ValueError("Total monthly obligations exceed 90% of income")
        return v

    @validator("scenario")
    def validate_scenario(cls, v):
        if not (-0.5 <= v.income_shock_pct <= 1.0):
            raise ValueError("income_shock_pct must be between -50% and +100%")
        if not (-0.5 <= v.payment_shock_pct <= 1.0):
            raise ValueError("payment_shock_pct must be between -50% and +100%")
        if v.mode != "target" and v.refinance is not None:
            raise ValueError("refinance is only allowed for target scenario")
        return v


# --------------------------
# Модели бизнес-расчёта
# --------------------------
class BusinessInput(BaseModel):
    ebitda: float
    interest: float
    principal: float
    taxes: float = 0
    currency: str = "RUB"
    meta: MetaSchema


class BusinessResult(BaseModel):
    calc_version: str
    currency: str
    monthly_debt_service: float
    cash_flow_proxy: float
    dcr: float
    pdn_business_percent: float
    risk_band: str
    meta: MetaSchema
    advice: str


# --------------------------
# Модель обновления конфигурации (админ)
# --------------------------
class PDNConfigUpdateSchema(BaseModel):
    credit_card_default_min_rate: Optional[float] = None
    rounding: Optional[int] = None
    risk_bands: Optional[dict] = None


# --------------------------
# Конфиг (динамический, изменяется через /admin/pdn/config)
# --------------------------
CONFIG = {
    "version": "v1.0",
    "risk_bands": {
        "low": {"max": 50.0},
        "mid": {"min": 50.0, "max": 80.0},
        "high": {"min": 80.0}
    },
    "rounding": {"money": 2, "percent": 2},
    "credit_card": {"default_min_payment_rate": 0.05}
}


def get_risk_band(percent: float) -> str:
    if percent < CONFIG["risk_bands"]["low"]["max"]:
        return "LOW"
    elif percent < CONFIG["risk_bands"]["mid"]["max"]:
        return "MID"
    return "HIGH"
