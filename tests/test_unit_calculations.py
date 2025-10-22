import pytest
from app.services import calculate_pdn
from app.models import PDNRequestSchema, ScenarioSchema

def test_basic_pdn_calculation():
    """Тест базового расчёта PDN."""
    req = PDNRequestSchema(
        subject_type="individual",
        income=100000,
        obligations=[{"amount": 20000, "type": "loan"}],
        scenario=ScenarioSchema(mode="base", shock_pct=0)
    )
    result = calculate_pdn(req)
    assert 0 < result.pdn_percent <= 100
    assert result.risk_band in ["low", "medium", "high"]

def test_validation_negative_income():
    """Доход не может быть отрицательным."""
    req = PDNRequestSchema(
        subject_type="individual",
        income=-1000,
        obligations=[],
        scenario=ScenarioSchema(mode="base", shock_pct=0)
    )
    with pytest.raises(ValueError):
        calculate_pdn(req)

def test_credit_card_obligation():
    """Кредитные карты должны считаться корректно."""
    req = PDNRequestSchema(
        subject_type="individual",
        income=100000,
        obligations=[{"amount": 5000, "type": "credit_card"}],
        scenario=ScenarioSchema(mode="base", shock_pct=0)
    )
    result = calculate_pdn(req)
    assert isinstance(result.pdn_percent, float)
