"""
Fraud Risk Scoring Rules Engine

Defines all individual red-flag rules, point values, categories,
and human-readable explainability metadata.
"""

from typing import Dict, Any, List, Optional
import re


def normalize_address(addr: Optional[str]) -> str:
    """Normalize address string for robust comparison."""
    if not addr:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", addr.lower())
    return " ".join(cleaned.split())


def extract_city(addr: Optional[str]) -> Optional[str]:
    """
    Extract common city names from address string if present,
    or identify the primary regional identifier.
    """
    if not addr:
        return None
    normalized = normalize_address(addr)
    known_cities = [
        "pune", "kolkata", "mumbai", "delhi", "bengaluru", "bangalore",
        "chennai", "hyderabad", "ahmedabad", "jaipur", "surat", "lucknow",
        "chandigarh", "indore", "kochi", "gurgaon", "noida", "new york",
        "los angeles", "chicago", "houston", "austin", "san francisco", "seattle"
    ]
    for city in known_cities:
        if city in normalized:
            # Map bangalore to bengaluru
            return "bengaluru" if city == "bangalore" else city
    
    # Fallback: check last token in comma-separated segment
    parts = [p.strip().lower() for p in addr.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[-1]
    return None


def is_address_mismatch(delivery_addr: Optional[str], return_addr: Optional[str]) -> bool:
    """
    Determines if the return/pickup address significantly differs from
    the original order delivery address.
    """
    if not delivery_addr or not return_addr:
        return False
    
    norm_del = normalize_address(delivery_addr)
    norm_ret = normalize_address(return_addr)
    
    if norm_del == norm_ret:
        return False
    
    city_del = extract_city(delivery_addr)
    city_ret = extract_city(return_addr)
    
    if city_del and city_ret and city_del != city_ret:
        return True
    
    # Check word overlap
    words_del = set(norm_del.split())
    words_ret = set(norm_ret.split())
    
    if not words_del or not words_ret:
        return False
    
    overlap = words_del.intersection(words_ret)
    union = words_del.union(words_ret)
    jaccard = len(overlap) / len(union) if union else 1.0
    
    # If less than 25% common terms, treat as distinct address
    return jaccard < 0.25


class RuleResult:
    """Result of evaluating an individual rule."""
    def __init__(
        self,
        rule_id: str,
        name: str,
        triggered: bool,
        points: int,
        reason: str,
        explanation: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.rule_id = rule_id
        self.name = name
        self.triggered = triggered
        self.points = points if triggered else 0
        self.max_points = points
        self.reason = reason
        self.explanation = explanation
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "triggered": self.triggered,
            "points": self.points,
            "max_points": self.max_points,
            "reason": self.reason,
            "explanation": self.explanation,
            "metadata": self.metadata,
        }


# ============================================================================
# Rule 1: High Return Rate (> 70% with sufficient order history)
# ============================================================================
class HighReturnRateRule:
    rule_id = "return_rate_too_high"
    name = "Extreme Return Rate (>70%)"
    max_points = 47
    category = "behavioral"
    explanation = (
        "Customer has returned over 70% of total lifetime purchases across 5+ orders. "
        "A typical customer returns 5-15% of orders. Sustained >70% rates signify systematic "
        "wardrobing or policy abuse."
    )

    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        total_orders = context.get("total_orders") or 0
        total_returns = context.get("total_returns") or 0

        if total_orders >= 5:
            rate = total_returns / total_orders
            if rate >= 0.70:
                pct = round(rate * 100, 1)
                # Base 35 points + graduated severity scaling up to 47 points for extreme rates (>=78%)
                if rate >= 0.78:
                    awarded_points = 47
                elif rate >= 0.75:
                    awarded_points = 42
                else:
                    awarded_points = 35

                return RuleResult(
                    rule_id=self.rule_id,
                    name=self.name,
                    triggered=True,
                    points=awarded_points,
                    reason=f"Return rate is {pct}% across {total_orders} orders (threshold: 70%, min 5 orders)",
                    explanation=self.explanation,
                    metadata={"rate": rate, "rate_pct": pct, "total_orders": total_orders, "total_returns": total_returns}
                )

        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            triggered=False,
            points=self.max_points,
            reason="Return rate within acceptable boundaries",
            explanation=self.explanation
        )



# ============================================================================
# Rule 2: Moderate Return Rate (50% - 70%)
# ============================================================================
class ModerateReturnRateRule:
    rule_id = "moderate_return_rate"
    name = "Elevated Return Rate (50%-70%)"
    max_points = 15
    category = "behavioral"
    explanation = (
        "Customer return rate is elevated between 50% and 70% with 4+ orders, "
        "indicating a higher propensity for returns than standard retail baselines."
    )

    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        total_orders = context.get("total_orders", 0)
        total_returns = context.get("total_returns", 0)

        # Only evaluate if high return rate rule did not trigger
        if total_orders >= 4:
            rate = total_returns / total_orders
            if 0.50 <= rate < 0.70:
                pct = round(rate * 100, 1)
                return RuleResult(
                    rule_id=self.rule_id,
                    name=self.name,
                    triggered=True,
                    points=self.max_points,
                    reason=f"Return rate is {pct}% across {total_orders} orders (elevated range 50%-70%)",
                    explanation=self.explanation,
                    metadata={"rate": rate, "rate_pct": pct, "total_orders": total_orders, "total_returns": total_returns}
                )

        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            triggered=False,
            points=self.max_points,
            reason="Return rate does not fall in elevated tier",
            explanation=self.explanation
        )


# ============================================================================
# Rule 3: Sudden Return Spike (Velocity check)
# ============================================================================
class SuddenReturnSpikeRule:
    rule_id = "sudden_return_spike"
    name = "Sudden Spike in Returns"
    max_points = 25
    category = "velocity"
    explanation = (
        "Customer suddenly initiated 3 or more returns within a 7-day period. "
        "Sudden velocity spikes often indicate account takeover, stolen credentials, "
        "or liquidation abuse."
    )

    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        returns_last_7_days = context.get("returns_last_7_days") or 0
        spike_flag = bool(context.get("has_return_spike"))

        if returns_last_7_days >= 3 or spike_flag:
            return RuleResult(
                rule_id=self.rule_id,
                name=self.name,
                triggered=True,
                points=self.max_points,
                reason=f"Spike detected: {returns_last_7_days} return requests initiated in the last 7 days",
                explanation=self.explanation,
                metadata={"returns_last_7_days": returns_last_7_days}
            )

        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            triggered=False,
            points=self.max_points,
            reason="Return velocity is normal",
            explanation=self.explanation
        )



# ============================================================================
# Rule 4: Delivery vs Return Address Mismatch
# ============================================================================
class AddressMismatchRule:
    rule_id = "address_mismatch"
    name = "Address Mismatch"
    max_points = 35
    category = "geographic"
    explanation = (
        "Item was delivered to one address, but refund/pickup is requested from an unrelated address. "
        "This pattern is heavily associated with package interception and unauthorized refund claims."
    )


    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        delivery_addr = context.get("delivery_address")
        return_addr = context.get("return_address")

        if delivery_addr and return_addr:
            if is_address_mismatch(delivery_addr, return_addr):
                return RuleResult(
                    rule_id=self.rule_id,
                    name=self.name,
                    triggered=True,
                    points=self.max_points,
                    reason=f"Delivery address ('{delivery_addr}') mismatches return pickup ('{return_addr}')",
                    explanation=self.explanation,
                    metadata={"delivery_address": delivery_addr, "return_address": return_addr}
                )

        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            triggered=False,
            points=self.max_points,
            reason="Delivery and return addresses match or are verified",
            explanation=self.explanation
        )


# ============================================================================
# Rule 5: Chronic Damaged Reason Abuse
# ============================================================================
class RepetitiveDamagedReasonRule:
    rule_id = "chronic_damaged_claims"
    name = "Repetitive Damaged Claims"
    max_points = 25
    category = "policy_abuse"
    explanation = (
        "Customer repeatedly claims 'item damaged' across returns. In retail logistics, genuine "
        "courier damage is rare (<3%). Continuous damaged claims indicate abuse of 'no-return required' "
        "or instant replacement policies."
    )

    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        current_reason = (context.get("return_reason") or "").lower()
        past_damaged_count = context.get("damaged_returns_count") or 0
        total_returns = context.get("total_returns") or 0

        # Trigger if:
        # 1. Current reason is damaged and customer has 2+ past damaged returns
        # 2. Or >= 70% of customer's returns were claimed damaged (with min 3 returns)
        if current_reason == "item_damaged" and past_damaged_count >= 2:
            return RuleResult(
                rule_id=self.rule_id,
                name=self.name,
                triggered=True,
                points=self.max_points,
                reason=f"Chronic defect claims: current claim is 'item_damaged' with {past_damaged_count} previous damaged claims",
                explanation=self.explanation,
                metadata={"past_damaged_count": past_damaged_count, "current_reason": current_reason}
            )

        if total_returns >= 3 and (past_damaged_count / total_returns) >= 0.70:
            return RuleResult(
                rule_id=self.rule_id,
                name=self.name,
                triggered=True,
                points=self.max_points,
                reason=f"{past_damaged_count} out of {total_returns} lifetime returns claimed 'item_damaged'",
                explanation=self.explanation,
                metadata={"past_damaged_count": past_damaged_count, "total_returns": total_returns}
            )

        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            triggered=False,
            points=self.max_points,
            reason="Damaged claims are within normal statistical tolerance",
            explanation=self.explanation
        )



# ============================================================================
# Rule 6: Wardrobing / Tag-Tucking Pattern
# ============================================================================
class WardrobingPatternRule:
    rule_id = "wardrobing_pattern"
    name = "Wardrobing / Rapid High-Value Return"
    max_points = 25
    category = "retail_fraud"
    explanation = (
        "Customer purchased a high-value item and requested a return within 72 hours of receipt, "
        "citing discretionary reasons (e.g., changed mind, wrong size). This strongly matches "
        "the retail 'wardrobing' profile (using merchandise for a one-time occasion and returning it)."
    )

    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        order_value = context.get("order_value", 0)
        days_since_delivery = context.get("days_since_delivery")
        days_since_purchase = context.get("days_since_purchase")
        reason = (context.get("return_reason") or "").lower()
        is_sale_period = context.get("is_sale_period", False)

        # Resolve duration
        duration = days_since_delivery if days_since_delivery is not None else days_since_purchase

        # Typical wardrobing reasons
        discretionary_reasons = {
            "changed_mind", "no_longer_needed", "wrong_size", "style_not_as_expected", "doesnt_fit"
        }

        # Thresholds: order_value >= 2000, duration <= 3 days, discretionary reason
        # Or if order_value >= 2500 and purchased during sale then returned <= 3 days
        if order_value >= 2000 and duration is not None and duration <= 3:
            if (reason in discretionary_reasons) or is_sale_period:
                return RuleResult(
                    rule_id=self.rule_id,
                    name=self.name,
                    triggered=True,
                    points=self.max_points,
                    reason=f"High-value order (₹{order_value:,.2f}) returned in {duration} days citing '{reason}'",
                    explanation=self.explanation,
                    metadata={"order_value": order_value, "duration_days": duration, "reason": reason}
                )

        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            triggered=False,
            points=self.max_points,
            reason="Does not exhibit rapid high-value wardrobing pattern",
            explanation=self.explanation
        )


# ============================================================================
# Rule 7: Brand New Customer High-Value Return
# ============================================================================
class NewCustomerHighValueRule:
    rule_id = "new_customer_high_value"
    name = "New Customer High-Value Return"
    max_points = 20
    category = "account_age"
    explanation = (
        "A brand-new customer account with no established positive transaction history "
        "initiating a return on a high-value order (₹2,500+). New accounts carry higher "
        "first-party fraud risk."
    )

    def evaluate(self, context: Dict[str, Any]) -> RuleResult:
        total_orders = context.get("total_orders", 0)
        order_value = context.get("order_value", 0)

        if total_orders <= 1 and order_value >= 2500:
            return RuleResult(
                rule_id=self.rule_id,
                name=self.name,
                triggered=True,
                points=self.max_points,
                reason=f"Brand new account (orders: {total_orders}) returning high-value item (₹{order_value:,.2f})",
                explanation=self.explanation,
                metadata={"total_orders": total_orders, "order_value": order_value}
            )

        return RuleResult(
            rule_id=self.rule_id,
            name=self.name,
            triggered=False,
            points=self.max_points,
            reason="Account has established history or order value is low",
            explanation=self.explanation
        )


# Registry of active rules
ACTIVE_RULES = [
    HighReturnRateRule(),
    ModerateReturnRateRule(),
    SuddenReturnSpikeRule(),
    AddressMismatchRule(),
    RepetitiveDamagedReasonRule(),
    WardrobingPatternRule(),
    NewCustomerHighValueRule(),
]
