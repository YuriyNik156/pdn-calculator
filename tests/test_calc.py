import pytest
from app.models import (
    PDNRequestSchema,
    IncomeSchema,
    ObligationSchema,
    ScenarioSchema,
    AssumptionsSchema,
)
from app.services import calculate_pdn, CalculationError

def test_example_A_from_spec():
    # Пример из ТЗ: доход 120000, ипотека 25000, авто 12000, карта 80000 (5% min), алименты 10000
    req = PDNRequestSchema(
        subject_type="individual",
        incomes=[IncomeSchema(source="salary", amount=120000, currency="RUB")],
        obligations=[
            ObligationSchema(type="loan", monthly_payment=25000),
            ObligationSchema(type="loan", monthly_payment=12000),
            ObligationSchema(type="credit_card", balance=80000, min_payment_rate=0.05),
            ObligationSchema(type="alimony", monthly_payment=10000),
        ],
        scenario=ScenarioSchema(mode="base"),
    )
    res = calculate_pdn(req)
    # monthly obligations total = 25000+12000+4000+10000 = 51000
    assert res.breakdown["monthly_obligations_total"] == 51000.0
    # PDN = 51000 / 120000 * 100 = 42.5% => 0.425 as fraction
    assert abs(res.pdn_ratio - 0.425) < 1e-6
    assert res.meta.risk_band == "LOW"

def test_example_stress_from_spec():
    req = PDNRequestSchema(
        subject_type="individual",
        incomes=[IncomeSchema(source="salary", amount=120000, currency="RUB")],
        obligations=[
            ObligationSchema(type="loan", monthly_payment=25000),
            ObligationSchema(type="loan", monthly_payment=12000),
            ObligationSchema(type="credit_card", balance=80000, min_payment_rate=0.05),
            ObligationSchema(type="alimony", monthly_payment=10000),
        ],
        scenario=ScenarioSchema(mode="stress", shock=0.1),  # payment_shock ~ +10%, income_shock ~ -10% in our simplification
    )
    res = calculate_pdn(req)
    # In our implementation, stress with shock=0.1 will increase payments and reduce income (see service logic)
    # we just assert that pdn is > 50% (as per TZ example)
    assert res.pdn_ratio * 100.0 > 50.0
    assert res.meta.risk_band in ("MID", "HIGH")

@pytest.mark.parametrize(
    "pdn_percent, expected_band",
    [
        (49.99, "LOW"),
        (50.0, "MID"),
        (80.0, "MID"),
        (80.01, "HIGH"),
    ],
)
def test_risk_thresholds(pdn_percent, expected_band):
    # Для установки точного PDN подставим доход и обязательства так, чтобы pdn_percent соблюдался.
    income_value = 100000.0
    monthly_obligations = income_value * (pdn_percent / 100.0)
    req = PDNRequestSchema(
        subject_type="individual",
        incomes=[IncomeSchema(source="salary", amount=income_value, currency="RUB")],
        obligations=[ObligationSchema(type="loan", monthly_payment=monthly_obligations)],
        scenario=ScenarioSchema(mode="base"),
    )
    res = calculate_pdn(req)
    assert res.meta.risk_band == expected_band

    