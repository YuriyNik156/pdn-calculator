import pytest
from app.models import (
    PDNRequestSchema,
    IncomeSchema,
    ObligationSchema,
    ScenarioSchema,
    MetaSchema,
)
from app.services import calculate_pdn, CalculationError


def test_pdn_base():
    req = PDNRequestSchema(
        subject_type="individual",
        income=IncomeSchema(source="salary", amount=100000, currency="RUB"),
        obligations=[ObligationSchema(type="loan", monthly_payment=40000, name="Кредит")],
        scenario=ScenarioSchema(mode="base"),
        meta=MetaSchema(client_id="test_client", request_id="req-1")
    )
    res = calculate_pdn(req)

    assert isinstance(res.pdn_percent, float)
    assert res.pdn_percent == 40.0
    assert res.risk_band == "LOW"
    assert len(res.breakdown) == 1
    assert res.currency == "RUB"
    assert res.scenario_applied == "base"
    assert res.calc_version == "v1.0"
    assert res.meta.client_id == "test_client"
    assert res.meta.request_id == "req-1"


def test_pdn_stress():
    req = PDNRequestSchema(
        subject_type="individual",
        income=IncomeSchema(source="salary", amount=100000, currency="RUB"),
        obligations=[ObligationSchema(type="loan", monthly_payment=40000, name="Кредит")],
        scenario=ScenarioSchema(mode="stress", income_shock_pct=-0.1, payment_shock_pct=0.1),
        meta=MetaSchema(client_id="test_client", request_id="req-2")
    )
    res = calculate_pdn(req)

    # PDN увеличивается при стрессовом сценарии
    assert res.pdn_percent > 40.0
    assert res.risk_band in ("MID", "HIGH")
    assert len(res.breakdown) == 1
    assert res.currency == "RUB"
    assert res.scenario_applied == "stress"
    assert res.calc_version == "v1.0"
    assert res.meta.client_id == "test_client"
    assert res.meta.request_id == "req-2"


@pytest.mark.parametrize(
    "pdn_value,expected_band",
    [
        (49.99, "LOW"),
        (50.0, "MID"),
        (80.0, "MID"),
        (80.01, "HIGH"),
    ]
)
def test_risk_band_thresholds(pdn_value, expected_band):
    # Создаём фиктивный запрос для теста
    req = PDNRequestSchema(
        subject_type="individual",
        income=IncomeSchema(source="salary", amount=100000, currency="RUB"),
        obligations=[ObligationSchema(type="loan", monthly_payment=pdn_value * 1000 / 100, name="Кредит")],
        scenario=ScenarioSchema(mode="base"),
        meta=MetaSchema(client_id="test_client", request_id="req-threshold")
    )
    res = calculate_pdn(req)
    assert res.risk_band == expected_band
