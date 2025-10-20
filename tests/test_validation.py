import pytest
from pydantic import ValidationError
from app.models import IncomeSchema, ObligationSchema, ScenarioSchema

def test_income_positive_amount():
    income = IncomeSchema(source="salary", amount=100000, currency="RUB")
    assert income.amount == 100000

def test_income_negative_amount_raises():
    with pytest.raises(ValidationError):
        IncomeSchema(source="salary", amount=-5000, currency="RUB")

def test_currency_code_length():
    with pytest.raises(ValidationError):
        IncomeSchema(source="rent", amount=20000, currency="RU")

def test_valid_obligation_with_monthly_payment():
    o = ObligationSchema(type="loan", monthly_payment=15000)
    assert o.monthly_payment == 15000

def test_obligation_with_balance_and_min_rate():
    o = ObligationSchema(type="credit_card", balance=100000, min_payment_rate=0.05)
    assert o.balance == 100000

def test_obligation_missing_required_fields():
    with pytest.raises(ValidationError):
        ObligationSchema(type="loan")

def test_shock_out_of_range():
    with pytest.raises(ValidationError):
        ScenarioSchema(mode="stress", shock=2.0)
