from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from uuid import uuid4

# --------------------------
# Схема дохода
# --------------------------
class IncomeSchema(BaseModel):
    amount: float
    currency: str = "RUB"
    income_type: Literal["net", "gross"] = "net"
    source: Literal["salary", "other"] = "salary"  # добавлено ограничение

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
    refinance: Optional[List[ObligationSchema]] = None  # добавлено для target

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
# Главная схема запроса
# --------------------------
class PDNRequestSchema(BaseModel):
    subject_type: Literal["individual", "business"] = "individual"
    period_months: int = Field(6, ge=1)
    income: IncomeSchema
    obligations: List[ObligationSchema]
    scenario: ScenarioSchema
    assumptions: Optional[AssumptionsSchema] = AssumptionsSchema()
    meta: MetaSchema

    # ----------------------
    # Валидируем доход
    # ----------------------
    @validator("income")
    def validate_income(cls, v):
        if v.amount <= 0:
            raise ValueError("income.amount must be > 0")
        allowed_currencies = ["RUB", "USD", "EUR"]  # пример ISO-4217
        if v.currency not in allowed_currencies:
            raise ValueError(f"Unsupported currency {v.currency}")
        return v

    # ----------------------
    # Валидируем обязательства
    # ----------------------
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

    # ----------------------
    # Валидируем сценарии
    # ----------------------
    @validator("scenario")
    def validate_scenario(cls, v):
        if not (-0.5 <= v.income_shock_pct <= 1.0):
            raise ValueError("income_shock_pct must be between -50% and +100%")
        if not (-0.5 <= v.payment_shock_pct <= 1.0):
            raise ValueError("payment_shock_pct must be between -50% and +100%")
        # Проверка refinance только для target
        if v.mode != "target" and v.refinance is not None:
            raise ValueError("refinance is only allowed for target scenario")
        return v
