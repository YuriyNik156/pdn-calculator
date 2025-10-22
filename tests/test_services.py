import pytest
from app.models import PDNRequestSchema, ObligationSchema
from app.services import calculate_pdn

def make_request(overrides=None):
    req_dict = {
        "subject_type": "individual",
        "period_months": 6,
        "income": {"amount": 120000, "currency": "RUB", "income_type": "net", "source": "salary"},
        "obligations": [
            {"type": "loan", "monthly_payment": 25000, "currency": "RUB", "name": "Ипотека"},
            {"type": "loan", "monthly_payment": 12000, "currency": "RUB", "name": "Автокредит"},
            {"type": "credit_card", "balance": 80000, "min_payment_rate": 0.05, "currency": "RUB", "name": "Visa"},
            {"type": "alimony", "monthly_payment": 10000, "currency": "RUB", "name": "Алименты"},
        ],
        "scenario": {"mode": "base", "income_shock_pct": 0, "payment_shock_pct": 0, "refinance": None},
        "assumptions": {"credit_card_default_min_rate": 0.05, "rounding": 2},
        "meta": {"client_id": "abc-123", "request_id": "req-1"}
    }
    if overrides:
        req_dict.update(overrides)
    return PDNRequestSchema.parse_obj(req_dict)

def test_pdn_base():
    req = make_request()
    result = calculate_pdn(req)
    assert result["pdn_percent"] > 0
    assert result["risk_band"] in ["LOW", "MID", "HIGH"]

def test_pdn_stress():
    req = make_request({"scenario": {"mode": "stress", "income_shock_pct": -0.2, "payment_shock_pct": 0.1, "refinance": None}})
    result = calculate_pdn(req)
    assert result["pdn_percent"] > 0

def test_pdn_target_refinance():
    refinance = [{"name": "Ипотека", "monthly_payment": 20000, "type": "loan"}]
    req = make_request({"scenario": {"mode": "target", "income_shock_pct": 0, "payment_shock_pct": 0, "refinance": refinance}})
    result = calculate_pdn(req)
    assert any(o["monthly"] == 20000 for o in result["breakdown"] if o["name"] == "Ипотека")

def test_risk_thresholds():
    # ПДН = 49.99% → LOW
    req = make_request({"income": {"amount": 102000, "currency": "RUB", "income_type": "net", "source": "salary"}})
    result = calculate_pdn(req)
    assert result["risk_band"] == "LOW"
    # ПДН = 50% → MID
    req = make_request({"income": {"amount": 100000, "currency": "RUB", "income_type": "net", "source": "salary"}})
    result = calculate_pdn(req)
    assert result["risk_band"] == "MID"
