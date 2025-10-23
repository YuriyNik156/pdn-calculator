# app/docs/examples.py
example_request = {
    "subject_type": "individual",
    "period_months": 6,
    "income": {"amount": 120000, "currency": "RUB", "income_type": "net", "source": "payroll"},
    "obligations": [
        {"type": "loan", "monthly_payment": 25000, "currency": "RUB", "name": "Ипотека"},
        {"type": "loan", "monthly_payment": 12000, "currency": "RUB", "name": "Автокредит"},
        {"type": "credit_card", "balance": 80000, "min_payment_rate": 0.05, "currency": "RUB", "name": "Visa"},
        {"type": "alimony", "monthly_payment": 10000, "currency": "RUB", "name": "Алименты"}
    ],
    "scenario": {"mode": "base", "income_shock_pct": 0, "payment_shock_pct": 0, "refinance": None},
    "assumptions": {"credit_card_default_min_rate": 0.05, "rounding": 2},
    "meta": {"client_id": "abc-123", "request_id": "uuid-here"}
}

example_response = {
    "calc_version": "v1.0",
    "currency": "RUB",
    "monthly_obligations_total": 47000,
    "monthly_income_used": 120000,
    "pdn_percent": 39.17,
    "risk_band": "LOW",
    "scenario_applied": "base",
    "advice": "Допустимая долговая нагрузка."
}
