"""
Unit Tests for Individual Fraud Detection Rules
"""

import pytest
from src.rules import (
    HighReturnRateRule,
    ModerateReturnRateRule,
    SuddenReturnSpikeRule,
    AddressMismatchRule,
    RepetitiveDamagedReasonRule,
    WardrobingPatternRule,
    NewCustomerHighValueRule,
    is_address_mismatch
)


def test_high_return_rate_triggers():
    rule = HighReturnRateRule()
    # 10 orders, 8 returns = 80% (>= 70% threshold, orders >= 5)
    ctx = {"total_orders": 10, "total_returns": 8}
    result = rule.evaluate(ctx)
    assert result.triggered is True
    assert result.points >= 35
    assert "80.0%" in result.reason


def test_high_return_rate_does_not_trigger_for_few_orders():
    rule = HighReturnRateRule()
    # 2 orders, 2 returns = 100%, but orders < 5 (insufficient sample size)
    ctx = {"total_orders": 2, "total_returns": 2}
    result = rule.evaluate(ctx)
    assert result.triggered is False
    assert result.points == 0


def test_moderate_return_rate_triggers():
    rule = ModerateReturnRateRule()
    # 10 orders, 6 returns = 60% (between 50% and 70%)
    ctx = {"total_orders": 10, "total_returns": 6}
    result = rule.evaluate(ctx)
    assert result.triggered is True
    assert result.points == 15


def test_address_mismatch_detection():
    # Exact match
    assert not is_address_mismatch("12 MG Road, Pune", "12 MG Road, Pune")
    # Case & formatting variations
    assert not is_address_mismatch("12 MG Road, Pune", "12 mg road, pune.")
    # Distinct cities
    assert is_address_mismatch("12 MG Road, Pune", "45 Park Street, Kolkata")
    assert is_address_mismatch("14 Marine Drive, Mumbai", "102 Connaught Place, New Delhi")


def test_address_mismatch_rule_evaluation():
    rule = AddressMismatchRule()
    ctx_mismatch = {
        "delivery_address": "12 MG Road, Pune",
        "return_address": "45 Park Street, Kolkata"
    }
    result = rule.evaluate(ctx_mismatch)
    assert result.triggered is True
    assert result.points == 35
    assert "mismatches" in result.reason


    ctx_match = {
        "delivery_address": "12 MG Road, Pune",
        "return_address": "12 MG Road, Pune"
    }
    result_match = rule.evaluate(ctx_match)
    assert result_match.triggered is False
    assert result_match.points == 0


def test_sudden_return_spike_triggers():
    rule = SuddenReturnSpikeRule()
    # 3 returns in last 7 days
    ctx = {"returns_last_7_days": 3}
    result = rule.evaluate(ctx)
    assert result.triggered is True
    assert result.points == 25

    # 1 return in last 7 days -> normal
    ctx_normal = {"returns_last_7_days": 1}
    assert rule.evaluate(ctx_normal).triggered is False


def test_repetitive_damaged_claims_triggers():
    rule = RepetitiveDamagedReasonRule()
    # Customer claiming damaged with 2 past damaged claims
    ctx = {
        "return_reason": "item_damaged",
        "damaged_returns_count": 2,
        "total_returns": 3
    }
    result = rule.evaluate(ctx)
    assert result.triggered is True
    assert result.points == 25

    # Customer claiming wrong_size with no prior damaged history
    ctx_clean = {
        "return_reason": "wrong_size",
        "damaged_returns_count": 0,
        "total_returns": 3
    }
    assert rule.evaluate(ctx_clean).triggered is False


def test_wardrobing_rule_triggers():
    rule = WardrobingPatternRule()
    # High value ₹3,500, returned in 2 days with 'changed_mind'
    ctx = {
        "order_value": 3500.0,
        "days_since_delivery": 2,
        "return_reason": "changed_mind"
    }
    result = rule.evaluate(ctx)
    assert result.triggered is True
    assert result.points == 25

    # Low value order ₹800 returned in 2 days -> not wardrobing
    ctx_cheap = {
        "order_value": 800.0,
        "days_since_delivery": 2,
        "return_reason": "changed_mind"
    }
    assert rule.evaluate(ctx_cheap).triggered is False

    # High value order returned after 14 days -> regular return window
    ctx_late = {
        "order_value": 3500.0,
        "days_since_delivery": 14,
        "return_reason": "changed_mind"
    }
    assert rule.evaluate(ctx_late).triggered is False


def test_new_customer_high_value_triggers():
    rule = NewCustomerHighValueRule()
    # 1st order with value ₹3,200
    ctx = {"total_orders": 1, "order_value": 3200.0}
    result = rule.evaluate(ctx)
    assert result.triggered is True
    assert result.points == 20

    # Established customer with 10 orders and value ₹3,200 -> established trust
    ctx_established = {"total_orders": 10, "order_value": 3200.0}
    assert rule.evaluate(ctx_established).triggered is False
