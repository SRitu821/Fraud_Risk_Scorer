"""
API Integration Tests for Fraud Risk Scorer REST Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from src.api import app
from src.database import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_score_return_high_risk_example_from_brief():
    """
    Test the exact input and expected response shape from the project brief:
    Input:
      customer_id: "CUST_1042"
      total_orders: 14
      total_returns: 11
      delivery_address: "12 MG Road, Pune"
      return_address: "45 Park Street, Kolkata"
      return_reason: "item_damaged"
      order_value: 2499
    Expected:
      risk_score: >= 61
      risk_level: "high"
      reasons: includes "return_rate_too_high", "address_mismatch"
      recommendation: "route_to_manual_review"
    """
    payload = {
        "customer_id": "CUST_1042",
        "total_orders": 14,
        "total_returns": 11,
        "delivery_address": "12 MG Road, Pune",
        "return_address": "45 Park Street, Kolkata",
        "return_reason": "item_damaged",
        "order_value": 2499.0
    }

    response = client.post("/api/score-return", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["customer_id"] == "CUST_1042"
    assert data["risk_score"] >= 61
    assert data["risk_level"] == "high"
    assert "return_rate_too_high" in data["reasons"]
    assert "address_mismatch" in data["reasons"]
    assert data["recommendation"] == "route_to_manual_review"
    assert "breakdown" in data
    assert "return_id" in data


def test_score_return_low_risk_auto_approve():
    """
    Test genuine shopper return: low return rate, matching addresses, normal size issue.
    Expected: low risk score, risk_level == 'low', recommendation == 'auto_approve'.
    """
    payload = {
        "customer_id": "CUST_GENUINE_99",
        "total_orders": 12,
        "total_returns": 1,
        "delivery_address": "88 Brigade Road, Bengaluru",
        "return_address": "88 Brigade Road, Bengaluru",
        "return_reason": "wrong_size",
        "order_value": 1100.0,
        "days_since_delivery": 7
    }

    response = client.post("/api/score-return", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["risk_score"] <= 30
    assert data["risk_level"] == "low"
    assert data["recommendation"] == "auto_approve"
    assert len(data["reasons"]) == 0


def test_get_rules_endpoint():
    response = client.get("/api/rules")
    assert response.status_code == 200
    rules = response.json()
    assert isinstance(rules, list)
    assert len(rules) >= 5

    rule_ids = [r["rule_id"] for r in rules]
    assert "return_rate_too_high" in rule_ids
    assert "address_mismatch" in rule_ids
    assert "chronic_damaged_claims" in rule_ids
    assert "wardrobing_pattern" in rule_ids


def test_get_stats_endpoint():
    response = client.get("/api/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_returns" in stats
    assert "low_risk_count" in stats
    assert "high_risk_count" in stats
    assert "high_risk_value_protected" in stats


def test_get_returns_queue_endpoint():
    response = client.get("/api/returns?risk_level=all&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "returns" in data
    assert "count" in data


def test_review_return_action():
    # First create a return
    payload = {
        "customer_id": "CUST_REVIEW_TEST",
        "total_orders": 8,
        "total_returns": 7,
        "delivery_address": "12 MG Road, Pune",
        "return_address": "45 Park Street, Kolkata",
        "return_reason": "item_damaged",
        "order_value": 2200.0,
        "save_record": True
    }
    score_resp = client.post("/api/score-return", json=payload)
    assert score_resp.status_code == 200
    ret_id = score_resp.json()["return_id"]

    # Now perform manual review decision
    review_resp = client.post(f"/api/returns/{ret_id}/review", json={"status": "approved"})
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "approved"

    # Reject decision
    reject_resp = client.post(f"/api/returns/{ret_id}/review", json={"status": "rejected"})
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"
