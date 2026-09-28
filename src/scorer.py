"""
Fraud Risk Scorer Core Engine

Aggregates individual rule outcomes, computes composite 0-100 risk score,
assigns standardized risk levels and automated routing recommendations,
and outputs full explainability breakdowns.
"""

from typing import Dict, Any, List, Optional
from src.rules import ACTIVE_RULES, RuleResult


def get_risk_level_and_recommendation(score: int) -> tuple[str, str]:
    """
    Map risk score (0-100) to operational risk level and recommendation.
    
    Tiers:
      0 - 30:  Low Risk    -> auto_approve
      31 - 60: Medium Risk -> light_review (or secondary verification)
      61 - 100: High Risk  -> route_to_manual_review
    """
    if score <= 30:
        return "low", "auto_approve"
    elif score <= 60:
        return "medium", "light_review"
    else:
        return "high", "route_to_manual_review"


def score_return_request(
    request_data: Dict[str, Any],
    rules: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """
    Evaluates a return or exchange request against all fraud rules.
    
    Args:
        request_data: Dictionary containing customer order & return context:
          - customer_id (str)
          - total_orders (int)
          - total_returns (int)
          - delivery_address (str)
          - return_address (str)
          - return_reason (str)
          - order_value (float)
          - days_since_delivery / days_since_purchase (int, optional)
          - returns_last_7_days (int, optional)
          - damaged_returns_count (int, optional)
          - is_sale_period (bool, optional)
        rules: Optional custom rule list, defaults to ACTIVE_RULES.
        
    Returns:
        Dictionary formatted according to project brief with:
          - customer_id: str
          - risk_score: int (0 - 100)
          - risk_level: 'low' | 'medium' | 'high'
          - reasons: list of triggered rule IDs
          - recommendation: 'auto_approve' | 'light_review' | 'route_to_manual_review'
          - breakdown: list of detailed trigger objects
    """
    if rules is None:
        rules = ACTIVE_RULES

    # Defensive type conversions and defaults
    context = dict(request_data)
    context["total_orders"] = int(context.get("total_orders") or 0)
    context["total_returns"] = int(context.get("total_returns") or 0)
    context["order_value"] = float(context.get("order_value") or 0.0)
    context["returns_last_7_days"] = int(context.get("returns_last_7_days") or 0)
    context["damaged_returns_count"] = int(context.get("damaged_returns_count") or 0)
    context["days_since_delivery"] = context.get("days_since_delivery")
    context["days_since_purchase"] = context.get("days_since_purchase")
    context["is_sale_period"] = bool(context.get("is_sale_period"))


    # If customer has a high return rate, we don't double count moderate return rate
    high_rate_triggered = False

    raw_score = 0
    reasons: List[str] = []
    breakdown: List[Dict[str, Any]] = []

    for rule in rules:
        # Avoid duplicate rate penalty if high return rate already caught it
        if rule.rule_id == "moderate_return_rate" and high_rate_triggered:
            continue

        result: RuleResult = rule.evaluate(context)

        if result.triggered:
            if rule.rule_id == "return_rate_too_high":
                high_rate_triggered = True

            raw_score += result.points
            reasons.append(result.rule_id)
            breakdown.append(result.to_dict())

    # Clamp composite score between 0 and 100
    final_score = max(0, min(100, raw_score))
    risk_level, recommendation = get_risk_level_and_recommendation(final_score)

    return {
        "customer_id": context.get("customer_id", "ANONYMOUS"),
        "risk_score": final_score,
        "risk_level": risk_level,
        "reasons": reasons,
        "recommendation": recommendation,
        "breakdown": breakdown,
        "total_rules_evaluated": len(rules),
        "triggered_count": len(reasons)
    }
