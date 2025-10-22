import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    r = client.get("/health")
    assert r.status_code == 200
    assert "message" in r.json()

def test_pdn_calc_contract():
    payload = {
        "subject_type": "individual",
        "income": 120000,
        "obligations": [{"amount": 30000, "type": "loan"}],
        "scenario": {"mode": "base", "shock_pct": 0}
    }
    r = client.post("/pdn/calc", json=payload)
    data = r.json()
    assert r.status_code == 200
    assert "data" in data
    assert "meta" in data
    assert "pdn_percent" in data["data"]
    assert "risk_band" in data["data"]
