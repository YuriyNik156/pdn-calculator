from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

from app.models import (
    PDNRequestSchema,
    CalcResultSchema,
    MetaSchema,
    ObligationSchema,
)

# Исключение при ошибке расчёта
class CalculationError(Exception):
    pass


# Константы / конфиг по умолчанию для MVP
DEFAULT_CC_MIN_RATE = 0.05  # 5%
DEFAULT_ROUNDING_MONEY = 2
DEFAULT_ROUNDING_PERCENT = 2


def _normalize_to_monthly(amount: float, period: Optional[str]) -> float:
    """
    Нормализует платеж к месячному эквиваленту.
    period: 'monthly'|'annual'|'quarterly'|'weekly'|'daily' (поддерживаем базовые)
    """
    if amount is None:
        return 0.0
    if not period:
        return float(amount)
    p = period.lower()
    if p in ("monthly", "month", "m"):
        return float(amount)
    if p in ("annual", "year", "y", "annually", "yearly"):
        return float(amount) / 12.0
    if p in ("quarterly", "quarter", "q"):
        return float(amount) / 3.0
    if p in ("weekly", "week", "w"):
        return float(amount) * 4.345  # среднее недель в месяце
    if p in ("daily", "day", "d"):
        return float(amount) * 30.436875  # среднее дней в месяце
    # неизвестный период — считаем как месячный
    return float(amount)


def _monthly_payment_from_obligation(
    obl: ObligationSchema, cc_default_min_rate: float = DEFAULT_CC_MIN_RATE, period: Optional[str] = "monthly"
) -> float:
    """
    Рассчитать ежемесячный платёж для одного обязательства.
    Для кредитной карты:
      - если monthly_payment указан и > 0 — используем его
      - иначе используем max(min_payment_rate, cc_default_min_rate) * balance
    Для прочих типов:
      - если monthly_payment задан — используем (с нормализацией по period)
      - иначе если есть balance и min_payment_rate — считаем аналогично
    """
    # Если явно задан monthly_payment — нормализуем и вернём
    if obl.monthly_payment is not None and obl.monthly_payment > 0:
        return _normalize_to_monthly(obl.monthly_payment, period)

    # Попытка посчитать по балансу и ставке (подходит для карт и других)
    if obl.balance is not None and (obl.min_payment_rate is not None):
        rate = max(float(obl.min_payment_rate), float(cc_default_min_rate))
        return _normalize_to_monthly(float(obl.balance) * rate, period)

    # Ничего посчитать нельзя — возврат 0 (но валидация должна была не допустить)
    return 0.0


def _sum_monthly_obligations(obligations: List[ObligationSchema], cc_default_min_rate: float = DEFAULT_CC_MIN_RATE, period_getter=None) -> Tuple[float, List[Dict]]:
    """
    Возвращает (total_monthly, breakdown_list).
    breakdown_list — список dict{name, monthly}
    Параметр period_getter может быть callable(obl)->str если у тебя будет поле period в модели.
    В нашей MVP модели поля period не было, поэтому будем считать платежы как ежемесячные (или использовать period_getter если передан).
    """
    total = 0.0
    breakdown = []
    for idx, obl in enumerate(obligations):
        period = None
        if period_getter:
            try:
                period = period_getter(obl)
            except Exception:
                period = None
        monthly = _monthly_payment_from_obligation(obl, cc_default_min_rate=cc_default_min_rate, period=period)
        total += monthly
        # имя в breakdown — если есть поле type, используем его и индекс
        name = getattr(obl, "type", f"obligation_{idx+1}")
        breakdown.append({"name": f"{name}", "monthly": monthly})
    return total, breakdown


def _apply_scenario(
    monthly_income: float, monthly_payments: float, scenario, assumptions=None
) -> Tuple[float, float]:
    """
    Применяет сценарий: base/stress/target.
    Для stress ожидаем, что scenario.shock — положительный/отрицательный процент для дохода или платежа.
    В ТЗ — два параметра: income_shock_pct и payment_shock_pct; в нашей упрощённой модели
    используем scenario.shock как общий мультипликатор для платежей (для демонстрации).
    Минимальная реализация: если scenario.mode == "stress" и scenario.shock задан,
      будем уменьшать доход (income *= 1 + income_shock_pct) при отрицательном шоке
      и увеличивать платежи (payments *= 1 + payment_shock_pct) если шок положительный.
    Здесь — если scenario.mode == "stress":
      - income *= (1 + income_shock_pct)  (income_shock_pct может быть отрицательным)
      - payments *= (1 + payment_shock_pct)
    Для простоты: если scenario имеет атрибуты income_shock_pct/payment_shock_pct — используем их,
    иначе если есть только shock — применяем его как payment_shock_pct и income_shock_pct = -abs(shock).
    """
    income_new = float(monthly_income)
    payments_new = float(monthly_payments)

    if scenario.mode == "base":
        return income_new, payments_new

    if scenario.mode == "stress":
        # Попробуем получить уникальные параметры, если они есть
        income_shock = getattr(scenario, "income_shock_pct", None)
        payment_shock = getattr(scenario, "payment_shock_pct", None)
        generic_shock = getattr(scenario, "shock", None)

        if income_shock is None and payment_shock is None and generic_shock is not None:
            # Предположим: generic_shock уменьшает доход и увеличивает платежи
            income_shock = generic_shock if generic_shock < 0 else -abs(generic_shock)
            payment_shock = generic_shock if generic_shock > 0 else abs(generic_shock)

        # Установим значения по умолчанию, если не заданы
        if income_shock is None:
            income_shock = 0.0
        if payment_shock is None:
            payment_shock = 0.0

        income_new = income_new * (1.0 + float(income_shock))
        payments_new = payments_new * (1.0 + float(payment_shock))
        return income_new, payments_new

    # target: минимальная реализация — если scenario.refinance присутствует, предполагаем,
    # что это список замен для payment (рефайнансирование), но если нет, ведём себя как base.
    if scenario.mode == "target":
        refinance = getattr(scenario, "refinance", None)
        if refinance and isinstance(refinance, list):
            # refinance — список dict {"idx": int, "new_monthly": float} или похожие.
            # В MVP мы не хотим усложнять: оставим как base (no-op),
            return income_new, payments_new
        return income_new, payments_new

    return income_new, payments_new


def _determine_risk_band(pdn_percent: float, assumptions=None) -> str:
    """
    Определяет risk_band по процентному значению pdn_percent (0-100).
    Используем пороги: LOW < 50, MID 50-80, HIGH > 80.
    Если assumptions содержит pdn_limit — используем его для LOW порога.
    """
    p = float(pdn_percent)
    low_thresh = 50.0
    mid_thresh = 80.0
    if assumptions:
        try:
            low_thresh = float(getattr(assumptions, "pdn_limit", 0.5)) * 100.0
        except Exception:
            low_thresh = 50.0
    if p < low_thresh:
        return "LOW"
    if low_thresh <= p <= mid_thresh:
        return "MID"
    return "HIGH"


def calculate_pdn(request: PDNRequestSchema) -> CalcResultSchema:
    """
    Основная функция расчёта.
    Возвращает объект CalcResultSchema или бросает CalculationError.
    """
    # Получаем месячный доход — в нашем MVP считаем, что в request.incomes[0].amount уже месячный
    if not request.incomes or len(request.incomes) == 0:
        raise CalculationError("No incomes provided")

    # Берём суммарный месячный доход (если несколько источников — суммируем)
    monthly_income = sum([float(i.amount) for i in request.incomes])

    if monthly_income <= 0:
        raise CalculationError("Income must be > 0")

    # Суммируем обязательства
    monthly_obligations_total, breakdown = _sum_monthly_obligations(request.obligations, cc_default_min_rate=DEFAULT_CC_MIN_RATE)

    # Применяем сценарий
    monthly_income_adj, monthly_payments_adj = _apply_scenario(monthly_income, monthly_obligations_total, request.scenario, request.assumptions)

    # Защита от деления на ноль
    if monthly_income_adj == 0:
        raise CalculationError("Monthly income after scenario adjustment is zero")

    # Рассчитываем pdn_percent (в процентах)
    pdn = (monthly_payments_adj / monthly_income_adj) * 100.0

    # Округления
    rounding_money = getattr(request.assumptions, "rounding_money", DEFAULT_ROUNDING_MONEY) if request.assumptions else DEFAULT_ROUNDING_MONEY
    rounding_percent = getattr(request.assumptions, "rounding_percent", DEFAULT_ROUNDING_PERCENT) if request.assumptions else DEFAULT_ROUNDING_PERCENT

    monthly_obligations_total = round(monthly_obligations_total, rounding_money)
    monthly_income_adj = round(monthly_income_adj, rounding_money)
    monthly_payments_adj = round(monthly_payments_adj, rounding_money)
    pdn_rounded = round(pdn, rounding_percent)

    # Определение risk_band
    risk_band = _determine_risk_band(pdn_rounded, request.assumptions)

    # Формируем advice/status
    status = "ok" if pdn_rounded < 50 else ("warning" if pdn_rounded < 80 else "error")
    advice = "Допустимая долговая нагрузка." if status == "ok" else ("Повышенная долговая нагрузка." if status == "warning" else "Критичное значение ПДН.")

    # Формируем meta
    meta = MetaSchema(
        ts=datetime.now(timezone.utc).isoformat(),
        calc_version=getattr(request.meta, "calc_version", "0.1.0") if request.meta else "0.1.0",
        risk_band=risk_band
    )
    
    # Расширяем breakdown (добавим суммарную линию)
    breakdown.append({"name": "TOTAL", "monthly": monthly_obligations_total})

    result = CalcResultSchema(
        pdn_ratio=round(pdn_rounded / 100.0, 4),  # как дробь 0-1 (модель требует 0..1)
        status=status,
        breakdown={"items": breakdown, "monthly_income_used": monthly_income_adj, "monthly_obligations_total": monthly_obligations_total},
        meta=meta,
    )

    return result

