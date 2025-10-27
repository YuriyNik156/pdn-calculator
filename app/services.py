from datetime import datetime, timezone
from app.models import (
    PDNRequestSchema,
    BusinessInput,
    BusinessResult,
    CONFIG,
    get_risk_band,
    MetaSchema,
)
from app.audit import log_request, log_response


def calculate_pdn(request: PDNRequestSchema):
    """
    Основная функция расчёта ПДН для физического лица.
    Принимает Pydantic-модель PDNRequestSchema.
    Возвращает словарь с расчётом и метаданными.
    """

    # Безопасное логирование входного запроса
    log_request(request.model_dump())

    # Исходные значения
    income_amount = request.income.amount
    obligations_breakdown = []

    # Перевод периодичности платежей к месяцу (на будущее)
    PERIOD_MAP = {
        "monthly": 1,
        "weekly": 4.345,   # 52 недели в год / 12 месяцев ≈ 4.345
        "quarterly": 1 / 3,
        "yearly": 1 / 12,
    }

    # Расчёт обязательств
    for obl in request.obligations:
        monthly = obl.monthly_payment
        period = getattr(obl, "period", "monthly")
        period_factor = PERIOD_MAP.get(period, 1)

        if monthly is None:
            if obl.type == "credit_card":
                rate = obl.min_payment_rate or request.assumptions.credit_card_default_min_rate
                monthly = (obl.balance or 0) * rate
            else:
                monthly = obl.balance or 0

        # Нормализация к месяцу
        monthly = monthly * period_factor

        # Применение шока по сценарию
        monthly *= 1 + request.scenario.payment_shock_pct

        obligations_breakdown.append({
            "id": getattr(obl, "id", None),
            "name": obl.name or obl.type,
            "monthly": round(monthly, request.assumptions.rounding)
        })

    # Применение рефинансирования (по id, если есть)
    if request.scenario.mode == "target" and request.scenario.refinance:
        for ref in request.scenario.refinance:
            for obl in obligations_breakdown:
                # Совпадение по id (если есть), иначе по имени (на всякий случай)
                if (obl.get("id") and ref.id == obl["id"]) or ref.name == obl["name"]:
                    new_payment = ref.monthly_payment or obl["monthly"]
                    obl["monthly"] = round(new_payment, request.assumptions.rounding)

    # Применяем шок по доходу
    income_amount *= 1 + request.scenario.income_shock_pct

    # Защита от деления на ноль
    if income_amount <= 0:
        raise ValueError("Income after shock is zero or negative — расчёт невозможен")

    # Итоговые значения
    total_monthly = sum(o["monthly"] for o in obligations_breakdown)
    pdn_percent = round((total_monthly / income_amount) * 100, request.assumptions.rounding)
    risk_band = get_risk_band(pdn_percent)

    advice = (
        "Допустимая долговая нагрузка."
        if pdn_percent <= 80
        else "Высокая долговая нагрузка."
    )

    # Формирование ответа
    response = {
        "calc_version": CONFIG["version"],
        "currency": request.income.currency,
        "monthly_obligations_total": total_monthly,
        "monthly_income_used": round(income_amount, request.assumptions.rounding),
        "pdn_percent": pdn_percent,
        "risk_band": risk_band,
        "breakdown": obligations_breakdown,
        "scenario_applied": request.scenario.mode,
        "advice": advice,
        "meta": {
            "client_id": request.meta.client_id,
            "request_id": request.meta.request_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Аудит (ответ)
    log_response(request.meta.request_id, response)
    return response


def calc_business_metrics(data: BusinessInput) -> BusinessResult:
    """
    Расчёт метрик долговой нагрузки для бизнеса (DCR и ПДН бизнеса).
    """

    monthly_debt_service = round(data.interest + data.principal, 2)
    cash_flow_proxy = round(data.ebitda - (data.taxes or 0), 2)

    if monthly_debt_service <= 0 or cash_flow_proxy <= 0:
        raise ValueError("Некорректные данные для расчёта DCR")

    dcr = round(cash_flow_proxy / monthly_debt_service, CONFIG["rounding"]["percent"])
    pdn_business = round((monthly_debt_service / cash_flow_proxy) * 100, CONFIG["rounding"]["percent"])
    risk_band = get_risk_band(pdn_business)

    advice = {
        "LOW": "Финансовая устойчивость высокая.",
        "MID": "Риск умеренный, стоит следить за долговой нагрузкой.",
        "HIGH": "Высокая долговая нагрузка, рекомендуется оптимизация расходов.",
    }[risk_band]

    return BusinessResult(
        calc_version=CONFIG["version"],
        currency=data.currency,
        monthly_debt_service=monthly_debt_service,
        cash_flow_proxy=cash_flow_proxy,
        dcr=dcr,
        pdn_business_percent=pdn_business,
        risk_band=risk_band,
        meta=data.meta or MetaSchema(client_id="unknown"),
        advice=advice,
    )


def get_config():
    """Возвращает текущий глобальный конфиг."""
    return CONFIG


def update_config(new_data: dict):
    """Обновляет глобальный конфиг и возвращает его."""
    CONFIG.update(new_data)
    return CONFIG


# app/services.py
def fx_convert(amount: float, from_currency: str, to_currency: str, rates: dict) -> float:
    """
    Простейшая функция конвертации валют.
    rates — словарь вида {'USD': 100.0, 'EUR': 110.0, 'RUB': 1.0}.
    """
    if from_currency == to_currency:
        return round(amount, 2)

    if from_currency not in rates or to_currency not in rates:
        raise ValueError(f"Unknown currency: {from_currency} or {to_currency}")

    base_amount = amount / rates[from_currency]
    converted = base_amount * rates[to_currency]
    return round(converted, 2)
