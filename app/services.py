from datetime import datetime
from app.models import PDNRequestSchema, BusinessInput, BusinessResult, CONFIG, get_risk_band, MetaSchema
from app.audit import log_request, log_response


def calculate_pdn(request: PDNRequestSchema):
    log_request(request.dict())

    income_amount = request.income.amount
    obligations_breakdown = []

    for obl in request.obligations:
        monthly = obl.monthly_payment
        if monthly is None:
            if obl.type == "credit_card":
                rate = obl.min_payment_rate or request.assumptions.credit_card_default_min_rate
                monthly = (obl.balance or 0) * rate
            else:
                monthly = obl.balance or 0
        monthly *= 1 + request.scenario.payment_shock_pct
        obligations_breakdown.append({
            "name": obl.name or obl.type,
            "monthly": round(monthly, request.assumptions.rounding)
        })

    if request.scenario.mode == "target" and request.scenario.refinance:
        for ref in request.scenario.refinance:
            for obl in obligations_breakdown:
                if obl["name"] == ref.name:
                    obl["monthly"] = round(ref.monthly_payment or obl["monthly"], request.assumptions.rounding)

    income_amount *= 1 + request.scenario.income_shock_pct
    total_monthly = sum(o["monthly"] for o in obligations_breakdown)
    pdn_percent = round((total_monthly / income_amount) * 100, request.assumptions.rounding)
    risk_band = get_risk_band(pdn_percent)
    advice = "Допустимая долговая нагрузка." if pdn_percent <= 80 else "Высокая долговая нагрузка."

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
            "ts": datetime.utcnow().isoformat() + "Z"
        }
    }

    log_response(request.meta.request_id, response)
    return response


def calc_business_metrics(data: BusinessInput) -> BusinessResult:
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
        "HIGH": "Высокая долговая нагрузка, рекомендуется оптимизация расходов."
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
        advice=advice
    )


def get_config():
    return CONFIG


def update_config(new_data: dict):
    CONFIG.update(new_data)
    return CONFIG
