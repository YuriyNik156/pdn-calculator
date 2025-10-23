from app.models import PDNRequestSchema, ObligationSchema
from app.audit import log_request, log_response
from datetime import datetime

def calculate_pdn(request: PDNRequestSchema):
    # Логируем входящий запрос (без ПДН, псевдонимизация client_id)
    log_request(request.dict())

    income_amount = request.income.amount
    obligations_breakdown = []

    # Применяем шоки и target refinance
    for obl in request.obligations:
        # Определяем базовый ежемесячный платёж
        monthly = obl.monthly_payment
        if monthly is None:
            if obl.type == "credit_card":
                rate = obl.min_payment_rate or request.assumptions.credit_card_default_min_rate
                monthly = (obl.balance or 0) * rate
            else:
                monthly = obl.balance or 0

        # Применяем шок платежей
        monthly *= 1 + request.scenario.payment_shock_pct

        obligations_breakdown.append({
            "name": obl.name or obl.type,
            "monthly": round(monthly, request.assumptions.rounding)
        })

    # Target scenario: заменяем платежи на refinance
    if request.scenario.mode == "target" and request.scenario.refinance:
        for ref in request.scenario.refinance:
            for obl in obligations_breakdown:
                if obl["name"] == ref.name:
                    obl["monthly"] = round(ref.monthly_payment or obl["monthly"], request.assumptions.rounding)

    # Применяем шок дохода
    income_amount *= 1 + request.scenario.income_shock_pct

    # Итоговая сумма обязательств
    total_monthly = sum(o["monthly"] for o in obligations_breakdown)

    # PDN %
    pdn_percent = round((total_monthly / income_amount) * 100, request.assumptions.rounding)

    # Определяем risk band
    if pdn_percent < 50:
        risk_band = "LOW"
    elif pdn_percent <= 80:
        risk_band = "MID"
    else:
        risk_band = "HIGH"

    # Совет по нагрузке
    advice = "Допустимая долговая нагрузка." if pdn_percent <= 80 else "Высокая долговая нагрузка."

    response = {
        "calc_version": "v1.0",
        "currency": request.income.currency,  # мультивалютность
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
            "ts": datetime.utcnow().isoformat() + "Z"
        }
    }

    # Логируем ответ (без pdn_percent и breakdown)
    log_response(request.meta.request_id, response)

    return response
