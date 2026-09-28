"""
Unit & Edge Case Tests for Fraud Risk Scoring Engine
"""

import pytest
from src.scorer import score_return_request, get_risk_level_and_recommendation


def test_edge_case_brand_new_customer_zero_history():
    """Brand new customer with 0 total orders and 0 returns (e.g. edge-case payload)."""
    req = {
        "customer_id": "CUST_NEW_001",
        "total_orders": 0,
        "total_returns": 0,
        "delivery_address": "88 Brigade Road, Bengaluru",
        "return_address": "88 Brigade Road, Bengaluru",
        "return_reason": "wrong_size",
        "order_value": 799.0
    }
    result = score_return_request(req)
    assert result["risk_score"] == 0
    assert result["risk_level"] == "low"
    assert result["recommendation"] == "auto_approve"
    assert len(result["reasons"]) == 0


def test_edge_case_customer_exactly_one_order_normal_value():
    """Customer with exactly 1 order, low-medium value."""
    req = {
        "customer_id": "CUST_ONE_ORDER",
        "total_orders": 1,
        "total_returns": 0,
        "delivery_address": "12 MG Road, Pune",
        "return_address": "12 MG Road, Pune",
        "return_reason": "wrong_size",
        "order_value": 1200.0,
        "days_since_delivery": 5
    }
    result = score_return_request(req)
    assert result["risk_score"] == 0
    assert result["risk_level"] == "low"
    assert result["recommendation"] == "auto_approve"


def test_edge_case_customer_exactly_one_order_high_value():
    """Brand new customer with 1 order but very high value merchandise."""
    req = {
        "customer_id": "CUST_NEW_HIGH",
        "total_orders": 1,
        "total_returns": 0,
        "delivery_address": "12 MG Road, Pune",
        "return_address": "12 MG Road, Pune",
        "return_reason": "wrong_size",
        "order_value": 3500.0,
        "days_since_delivery": 5
    }
    result = score_return_request(req)
    assert result["risk_score"] == 20
    assert result["risk_level"] == "low"  # 20 <= 30 is low
    assert "new_customer_high_value" in result["reasons"]


def test_exact_seventy_percent_return_rate_boundary():
    """Boundary test: exactly 70.0% return rate (7 returns out of 10 orders)."""
    req = {
        "customer_id": "CUST_BOUNDARY_70",
        "total_orders": 10,
        "total_returns": 7,
        "delivery_address": "14 Marine Drive, Mumbai",
        "return_address": "14 Marine Drive, Mumbai",
        "return_reason": "wrong_size",
        "order_value": 1500.0,
        "days_since_delivery": 10
    }
    result = score_return_request(req)
    # Should trigger high return rate rule (35 pts)
    assert "return_rate_too_high" in result["reasons"]
    assert result["risk_score"] == 35
    assert result["risk_level"] == "medium"



def test_multiple_rules_triggered_and_score_capping():
    """
    Test customer triggering multiple severe rules simultaneously:
    - Extreme return rate (>70%): 30 pts
    - Address mismatch: 25 pts
    - Chronic damaged claims: 25 pts
    - Sudden return spike: 25 pts
    - Wardrobing pattern: 25 pts
    Total raw points = 130 pts.
    Result MUST be strictly capped at 100 max.
    """
    req = {
        "customer_id": "CUST_SUPER_FRAUD",
        "total_orders": 14,
        "total_returns": 12,
        "delivery_address": "12 MG Road, Pune",
        "return_address": "45 Park Street, Kolkata",
        "return_reason": "item_damaged",
        "order_value": 3200.0,
        "days_since_delivery": 2,
        "damaged_returns_count": 4,
        "returns_last_7_days": 4,
        "is_sale_period": True
    }
    result = score_return_request(req)
    assert result["risk_score"] == 100  # Capped at 100
    assert result["risk_level"] == "high"
    assert result["recommendation"] == "route_to_manual_review"
    assert "return_rate_too_high" in result["reasons"]
    assert "address_mismatch" in result["reasons"]
    assert "chronic_damaged_claims" in result["reasons"]
    assert "sudden_return_spike" in result["reasons"]
    assert "wardrobing_pattern" in result["reasons"]
    assert len(result["reasons"]) >= 5



def test_risk_level_and_recommendation_tiers():
    # 0-30: low, auto_approve
    assert get_risk_level_and_recommendation(0) == ("low", "auto_approve")
    assert get_risk_level_and_recommendation(30) == ("low", "auto_approve")
    
    # 31-60: medium, light_review
    assert get_risk_level_and_recommendation(31) == ("medium", "light_review")
    assert get_risk_level_and_recommendation(60) == ("medium", "light_review")

    # 61-100: high, route_to_manual_review
    assert get_risk_level_and_recommendation(61) == ("high", "route_to_manual_review")
    assert get_risk_level_and_recommendation(100) == ("high", "route_to_manual_review")


def test_project_brief_sample_case():
    """Verify the exact sample case from the project brief."""
    brief_req = {
        "customer_id": "CUST_1042",
        "total_orders": 14,
        "total_returns": 11,
        "delivery_address": "12 MG Road, Pune",
        "return_address": "45 Park Street, Kolkata",
        "return_reason": "item_damaged",
        "order_value": 2499.0,
        "damaged_returns_count": 2,
        "days_since_delivery": 2
    }
    result = score_return_request(brief_req)
    assert result["risk_level"] == "high"
    assert "return_rate_too_high" in result["reasons"]
    assert "address_mismatch" in result["reasons"]
    assert result["recommendation"] == "route_to_manual_review"
    assert result["risk_score"] >= 61
