import pytest
from app.services import calculate_pdn
from app.models import PDNRequestSchema, ScenarioSchema

def make_request(income, obligations):
    return PDNRequestSchema(
        subject_type="individual",
        income=income,
        obligations=obligations,
        scenario=ScenarioSchema(mode="base", shock_pct=0)
    )

def test_zero_income():
    req = make_request(0, [{"amount": 1000, "type": "loan"}])
    with pytest.raises(ValueError):
        calculate_pdn(req)

def test_zero_obligations():
    req = make_request(100000, [])
    result = calculate_pdn(req)
    assert result.pdn_percent == 0
    assert result.risk_band == "low"

def test_negative_obligation():
    req = make_request(100000, [{"amount": -5000, "type": "loan"}])
    with pytest.raises(ValueError):
        calculate_pdn(req)

def test_risk_band_boundaries():
    """Проверяем границы risk_band."""
    req = make_request(100000, [{"amount": 80000, "type": "loan"}])
    result = calculate_pdn(req)
    assert result.risk_band in ["medium", "high"]
