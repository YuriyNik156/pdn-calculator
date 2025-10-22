import pytest
from app.services import calculate_pdn
from app.models import PDNRequestSchema

def make_request():
    return PDNRequestSchema.parse_obj({
        "subject_type": "individual",
        "period_months": 6,
        "income": {"amount": 120000, "currency": "RUB", "income_type": "net", "source": "salary"},
        "obligations": [
            {"type": "loan", "monthly_payment": 25000, "currency": "RUB", "name": "Ипотека"}
        ],
        "scenario": {"mode": "base", "income_shock_pct": 0, "payment_shock_pct": 0, "refinance": None},
        "assumptions": {"credit_card_default_min_rate": 0.05, "rounding": 2},
        "meta": {"client_id": "abc-123", "request_id": "req-load"}
    })

def test_pdn_perf(benchmark):
    req = make_request()
    result = benchmark(lambda: calculate_pdn(req))
    assert result["pdn_percent"] > 0
