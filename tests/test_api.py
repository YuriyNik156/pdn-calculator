import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_pdn_calc_base():
    payload = {
        "subject_type": "individual",
        "period_months": 6,
        "income": {"amount": 120000, "currency": "RUB", "income_type": "net", "source": "salary"},
        "obligations": [
            {"type": "loan", "monthly_payment": 25000, "currency": "RUB", "name": "Ипотека"}
        ],
        "scenario": {"mode": "base", "income_shock_pct": 0, "payment_shock_pct": 0, "refinance": None},
        "assumptions": {"credit_card_default_min_rate": 0.05, "rounding": 2},
        "meta": {"client_id": "abc-123", "request_id": "req-123"}
    }
    r = client.post("/pdn/calc", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "pdn_percent" in data
    assert "risk_band" in data
    assert "calc_version" in data


def test_api_version_header():
    payload = {
        "subject_type": "individual",
        "period_months": 6,
        "income": {"amount": 120000, "currency": "RUB", "income_type": "net", "source": "salary"},
        "obligations": [
            {"type": "loan", "monthly_payment": 25000, "currency": "RUB", "name": "Ипотека"}
        ],
        "scenario": {"mode": "base", "income_shock_pct": 0, "payment_shock_pct": 0, "refinance": None},
        "assumptions": {"credit_card_default_min_rate": 0.05, "rounding": 2},
        "meta": {"client_id": "abc-123", "request_id": "req-123"}
    }
    r = client.post("/pdn/calc", json=payload)
    assert r.status_code == 200
    assert "X-PDN-Calc-Version" in r.headers


def test_validation_error():
    payload = {"income": {"amount": -1000, "currency": "RUB"}}
    r = client.post("/pdn/calc", json=payload)
    assert r.status_code == 422

def test_audit_endpoint():
    r = client.get("/admin/pdn/audit", params={"request_id": "req-123"})
    assert r.status_code == 200
    data = r.json()
    assert "logs" in data

def test_config_endpoint():
    r = client.get("/pdn/config")
    assert r.status_code == 200
    data = r.json()
    assert "risk_bands" in data
    assert "version" in data
