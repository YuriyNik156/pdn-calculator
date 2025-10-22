from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from app.models import (
    PDNRequestSchema,
    CalcResultSchema,
    MetaSchema,
    ObligationSchema,
    ScenarioSchema,
    AssumptionsSchema,
)

# Исключение при ошибке расчёта
class CalculationError(Exception):
    pass


# --- Константы по умолчанию ---
DEFAULT_CC_MIN_RATE = 0.05  # 5%
DEFAULT_ROUNDING_MONEY = 2
DEFAULT_ROUNDING_PERCENT = 2


# --- Вспомогательные функции ---
def _normalize_to_monthly(amount: float, period: Optional[str] = "monthly") -> float:
    if not period or period.lower() in ["monthly", "month", "m"]:
        return float(amount)
    if period.lower() in ["annual", "year", "y", "annually", "yearly"]:
        return float(amount) / 12.0
    if period.lower() in ["quarterly", "quarter", "q"]:
        return float(amount) / 3.0
    if period.lower() in ["weekly", "week", "w"]:
        return float(amount) * 4.345
    if period.lower() in ["daily", "day", "d"]:
        return float(amount) * 30.436875
    return float(amount)


def _monthly_payment_from_obligation(
    obl: ObligationSchema,
    cc_default_min_rate: float = DEFAULT_CC_MIN_RATE,
    period: Optional[str] = "monthly",
) -> float:
    """
    Рассчитать ежемесячный платёж для одного обязательства.
    """
    if obl.monthly_payment is not None and obl.monthly_payment > 0:
        return _normalize_to_monthly(obl.monthly_payment, period)

    if obl.type == "credit_card" and obl.balance is not None:
        rate = max(obl.min_payment_rate or 0.0, cc_default_min_rate)
        return _normalize_to_monthly(float(obl.balance) * rate, period)

    if obl.balance is not None and obl.min_payment_rate is not None:
        rate = max(obl.min_payment_rate, cc_default_min_rate)
        return _normalize_to_monthly(float(obl.balance) * rate, period)

    return 0.0


def _sum_monthly_obligations(
    obligations: List[ObligationSchema], cc_default_min_rate: float = DEFAULT_CC_MIN_RATE
) -> Tuple[float, List[Dict]]:
    """
    Возвращает сумму ежемесячных платежей и breakdown.
    """
    total = 0.0
    breakdown = []

    for obl in obligations:
        monthly = _monthly_payment_from_obligation(obl, cc_default_min_rate=cc_default_min_rate)
        total += monthly
        # Формируем название для breakdown
        if obl.type == "credit_card" and obl.min_payment_rate:
            name = f"{obl.name} (min {int(obl.min_payment_rate * 100)}%)"
        else:
            name = obl.name
        breakdown.append({"name": name, "monthly": round(monthly, 2)})

    return total, breakdown


def _apply_scenario(
    monthly_income: float, monthly_payments: float, scenario: ScenarioSchema
) -> Tuple[float, float]:
    """
    Применяем сценарий: base, stress, target.
    """
    income_adj = monthly_income
    payments_adj = monthly_payments

    if scenario.mode == "base":
        return income_adj, payments_adj

    if scenario.mode == "stress":
        income_shock = getattr(scenario, "income_shock_pct", 0.0)
        payment_shock = getattr(scenario, "payment_shock_pct", 0.0)

        income_adj *= 1.0 + float(income_shock)
        payments_adj *= 1.0 + float(payment_shock)
        return income_adj, payments_adj

    if scenario.mode == "target":
        # target с рефинансированием
        refinance = getattr(scenario, "refinance", None)
        if refinance and isinstance(refinance, list):
            for item in refinance:
                idx = item.get("idx")
                new_monthly = item.get("new_monthly")
                if idx is not None and 0 <= idx < len(monthly_payments):
                    payments_adj = monthly_payments - monthly_payments[idx] + new_monthly
        return income_adj, payments_adj

    return income_adj, payments_adj


def _determine_risk_band(pdn_percent: float, assumptions: Optional[AssumptionsSchema] = None) -> str:
    """
    Определяет risk_band по pdn_percent.
    """
    low_thresh = 50.0
    mid_thresh = 80.0
    if assumptions and hasattr(assumptions, "pdn_limit"):
        low_thresh = float(getattr(assumptions, "pdn_limit", 0.5)) * 100

    if pdn_percent < low_thresh:
        return "LOW"
    if low_thresh <= pdn_percent <= mid_thresh:
        return "MID"
    return "HIGH"


# --- Основная функция расчёта ---
def calculate_pdn(request: PDNRequestSchema) -> CalcResultSchema:
    if not request.income or request.income.amount <= 0:
        raise CalculationError("Income.amount must be > 0")

    monthly_income = float(request.income.amount)
    cc_default_rate = getattr(request.assumptions, "credit_card_default_min_rate", DEFAULT_CC_MIN_RATE) \
        if request.assumptions else DEFAULT_CC_MIN_RATE

    # Суммируем обязательства
    monthly_obligations_total, breakdown = _sum_monthly_obligations(request.obligations, cc_default_min_rate=cc_default_rate)

    # Применяем сценарий
    monthly_income_adj, monthly_payments_adj = _apply_scenario(monthly_income, monthly_obligations_total, request.scenario)

    if monthly_income_adj <= 0:
        raise CalculationError("Monthly income after scenario adjustment is zero")

    pdn_percent = round((monthly_payments_adj / monthly_income_adj) * 100, 2)

    # Определяем risk_band
    risk_band = _determine_risk_band(pdn_percent, request.assumptions)

    # Статус и совет
    status = "ok" if pdn_percent < 50 else ("warning" if pdn_percent < 80 else "error")
    advice = "Допустимая долговая нагрузка." if status == "ok" else \
             ("Повышенная долговая нагрузка." if status == "warning" else "Критичное значение ПДН.")

    # Meta
    meta = MetaSchema(
        ts=datetime.now(timezone.utc).isoformat(),
        calc_version=getattr(request.meta, "calc_version", "v1.0") if request.meta else "v1.0",
    )

    # Возвращаем результат
    result = CalcResultSchema(
        pdn_percent=pdn_percent,
        monthly_income_used=round(monthly_income_adj, 2),
        monthly_obligations_total=round(monthly_payments_adj, 2),
        risk_band=risk_band,
        breakdown=breakdown,
        advice=advice,
        meta=meta
    )

    return result
