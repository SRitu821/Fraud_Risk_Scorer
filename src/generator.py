"""
Synthetic Dataset Generator for Fraud Risk Scorer

Generates a realistic e-commerce database with customers, orders, and returns.
Deliberately introduces 5-10% fraudulent behavioral archetypes:
  1. Serial Returners (extreme return rate > 70%)
  2. Damage Claim Abusers (chronic 'item_damaged' claims)
  3. Address Mismatchers (delivery city != return city)
  4. Wardrobers (high-value items returned within 72h)
  5. Return Spikers (sudden rapid flurry of returns)
"""

import random
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database import init_db, get_db_connection, DB_PATH
from src.scorer import score_return_request


# Seed for reproducibility
random.seed(42)

FIRST_NAMES = [
    "Aarav", "Aditi", "Rohan", "Pooja", "Vikram", "Sneha", "Rahul", "Priya",
    "Ananya", "Karan", "Divya", "Siddharth", "Neha", "Arjun", "Kavita", "Amit",
    "Meera", "Varun", "Tanvi", "Rishi", "Deepa", "Manish", "Shreya", "Naveen",
    "Alex", "Jordan", "Taylor", "Morgan", "Sam", "Chris", "Pat", "Riley"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Mehta", "Deshmukh", "Nair", "Reddy", "Iyer",
    "Mukherjee", "Gupta", "Malhotra", "Joshi", "Kulkarni", "Bose", "Chopra", "Singh",
    "Smith", "Johnson", "Miller", "Davis", "Wilson", "Anderson", "Taylor", "Thomas"
]

CITIES = [
    ("Pune", "12 MG Road, Pune"),
    ("Kolkata", "45 Park Street, Kolkata"),
    ("Bengaluru", "88 Brigade Road, Bengaluru"),
    ("New Delhi", "102 Connaught Place, New Delhi"),
    ("Mumbai", "14 Marine Drive, Mumbai"),
    ("Chennai", "56 Anna Salai, Chennai"),
    ("Hyderabad", "77 Banjara Hills, Hyderabad"),
    ("Ahmedabad", "23 SG Highway, Ahmedabad"),
    ("Jaipur", "91 MI Road, Jaipur"),
]

ITEM_CATEGORIES = [
    "Apparel & Fashion", "Electronics", "Luxury Watches", "Footwear",
    "Home & Kitchen", "Beauty & Fragrance", "Sporting Goods", "Jewelry"
]

RETURN_REASONS = [
    "wrong_size", "changed_mind", "item_damaged", "color_different",
    "not_as_pictured", "defective_part", "arrived_late", "no_longer_needed"
]


def generate_synthetic_data(
    num_customers: int = 1200,
    db_path: str = DB_PATH,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Generate synthetic database of customers, orders, and returns.
    Inserts directly into SQLite database with full scoring evaluation.
    """
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Clear existing data for fresh seed
    cursor.execute("DELETE FROM returns")
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM customers")
    conn.commit()

    if verbose:
        print(f"Generating {num_customers} customers and associated orders/returns...")

    now_utc = datetime.now(timezone.utc)
    base_date = now_utc - timedelta(days=180)

    # Customer archetype distributions:
    # 86% normal
    # 4% serial_returner (high return rate + damaged reason / address mismatch)
    # 3% damage_abuser (chronic damaged claims + spike)
    # 3% address_mismatcher (address mismatch + wardrobing or high return rate)
    # 2% wardrober (high order value, rapid return, address/spike)
    # 2% spiker (spike + damage/mismatch)
    customer_records: List[Dict[str, Any]] = []
    order_records: List[Dict[str, Any]] = []
    return_records: List[Dict[str, Any]] = []

    for i in range(1, num_customers + 1):
        cust_id = f"CUST_{1000 + i}"
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{random.randint(10, 999)}@example.com"
        
        city_tuple = random.choice(CITIES)
        delivery_addr = city_tuple[1]

        # Determine archetype
        rand_val = random.random()
        if rand_val < 0.86:
            archetype = "normal"
            num_orders = random.randint(2, 14)
            return_propensity = random.uniform(0.04, 0.16)
        elif rand_val < 0.90:
            archetype = "serial_returner"
            num_orders = random.randint(7, 18)
            return_propensity = random.uniform(0.75, 0.95)
        elif rand_val < 0.93:
            archetype = "damage_abuser"
            num_orders = random.randint(5, 12)
            return_propensity = random.uniform(0.60, 0.85)
        elif rand_val < 0.95:
            archetype = "address_mismatcher"
            num_orders = random.randint(4, 10)
            return_propensity = random.uniform(0.40, 0.70)
        elif rand_val < 0.98:
            archetype = "wardrober"
            num_orders = random.randint(3, 8)
            return_propensity = random.uniform(0.50, 0.80)
        else:
            archetype = "spiker"
            num_orders = random.randint(5, 12)
            return_propensity = random.uniform(0.50, 0.75)

        # Generate orders for customer
        cust_orders = []
        cust_returns = []
        cust_damaged_returns = 0

        for o_idx in range(1, num_orders + 1):
            order_id = f"ORD_{10000 + len(order_records) + 1}"
            days_ago = random.randint(5, 175)
            order_date = base_date + timedelta(days=days_ago)

            # Order value depends on archetype
            if archetype in ("wardrober", "serial_returner") and random.random() < 0.6:
                order_val = round(random.uniform(2600.0, 7800.0), 2)
                category = random.choice(["Apparel & Fashion", "Luxury Watches", "Jewelry", "Electronics"])
            else:
                order_val = round(random.uniform(499.0, 3499.0), 2)
                category = random.choice(ITEM_CATEGORIES)

            order_records.append({
                "order_id": order_id,
                "customer_id": cust_id,
                "order_date": order_date.isoformat(),
                "order_value": order_val,
                "delivery_address": delivery_addr,
                "item_category": category,
                "status": "delivered"
            })
            cust_orders.append((order_id, order_val, order_date, category))

        # Decide which orders are returned based on propensity
        orders_to_return = []
        for ord_info in cust_orders:
            if random.random() < return_propensity:
                orders_to_return.append(ord_info)

        # Ensure serial returner triggers high return rate (>70% on 5+ orders)
        if archetype == "serial_returner" and len(cust_orders) >= 5:
            min_returns_needed = int(len(cust_orders) * 0.75) + 1
            if len(orders_to_return) < min_returns_needed:
                orders_to_return = cust_orders[:min_returns_needed]

        # Generate return records
        for ret_idx, (ord_id, ord_val, ord_date, cat) in enumerate(orders_to_return):
            ret_id = f"RET_{10000 + len(return_records) + 1}"

            # Default return timing and address
            days_after_purchase = random.randint(4, 14)
            ret_date = ord_date + timedelta(days=days_after_purchase)
            ret_addr = delivery_addr
            reason = random.choice(RETURN_REASONS)
            has_spike = False

            # Compound suspicious behaviors
            if archetype == "damage_abuser":
                reason = "item_damaged"
                cust_damaged_returns += 1
                # Often also has address mismatch or sudden spike
                if random.random() < 0.5:
                    diff_city = random.choice([c for c in CITIES if c[1] != delivery_addr])
                    ret_addr = diff_city[1]
                if ret_idx >= 2 and random.random() < 0.4:
                    has_spike = True

            elif archetype == "address_mismatcher":
                # Select a different city
                diff_city = random.choice([c for c in CITIES if c[1] != delivery_addr])
                ret_addr = diff_city[1]
                if random.random() < 0.5:
                    reason = "item_damaged"
                    cust_damaged_returns += 1
                else:
                    reason = random.choice(["wrong_size", "changed_mind", "not_as_pictured"])

            elif archetype == "serial_returner":
                if random.random() < 0.45:
                    diff_city = random.choice([c for c in CITIES if c[1] != delivery_addr])
                    ret_addr = diff_city[1]
                if random.random() < 0.4:
                    reason = "item_damaged"
                    cust_damaged_returns += 1
                else:
                    reason = random.choice(["wrong_size", "changed_mind"])

            elif archetype == "wardrober":
                days_after_purchase = random.randint(1, 3)
                ret_date = ord_date + timedelta(days=days_after_purchase)
                reason = random.choice(["changed_mind", "no_longer_needed", "style_not_as_expected"])
                if random.random() < 0.45:
                    diff_city = random.choice([c for c in CITIES if c[1] != delivery_addr])
                    ret_addr = diff_city[1]

            elif archetype == "spiker":
                ret_date = now_utc - timedelta(days=random.randint(1, 5))
                has_spike = True
                if random.random() < 0.5:
                    reason = "item_damaged"
                    cust_damaged_returns += 1
                else:
                    reason = random.choice(["changed_mind", "wrong_size"])
                if random.random() < 0.4:
                    diff_city = random.choice([c for c in CITIES if c[1] != delivery_addr])
                    ret_addr = diff_city[1]

            else:
                # Normal shopper
                if reason == "item_damaged":
                    cust_damaged_returns += 1

            spike_count = 3 if has_spike else (3 if (now_utc - ret_date).days <= 7 and len(orders_to_return) >= 3 else 0)

            score_input = {
                "customer_id": cust_id,
                "order_id": ord_id,
                "total_orders": len(cust_orders),
                "total_returns": ret_idx + 1,
                "delivery_address": delivery_addr,
                "return_address": ret_addr,
                "return_reason": reason,
                "order_value": ord_val,
                "days_since_delivery": days_after_purchase,
                "days_since_purchase": days_after_purchase,
                "damaged_returns_count": cust_damaged_returns,
                "returns_last_7_days": spike_count,
                "has_return_spike": has_spike
            }

            score_res = score_return_request(score_input)

            return_records.append({
                "return_id": ret_id,
                "order_id": ord_id,
                "customer_id": cust_id,
                "request_date": ret_date.isoformat(),
                "delivery_address": delivery_addr,
                "return_address": ret_addr,
                "return_reason": reason,
                "order_value": ord_val,
                "risk_score": score_res["risk_score"],
                "risk_level": score_res["risk_level"],
                "recommendation": score_res["recommendation"],
                "reasons": score_res["reasons"],
                "breakdown": score_res["breakdown"],
            })
            cust_returns.append(ret_id)


        customer_records.append({
            "customer_id": cust_id,
            "name": name,
            "email": email,
            "delivery_address": delivery_addr,
            "total_orders": len(cust_orders),
            "total_returns": len(cust_returns),
            "customer_type": archetype
        })

    # Batch insert into database
    import json
    cursor.executemany("""
        INSERT INTO customers (customer_id, name, email, delivery_address, total_orders, total_returns, customer_type)
        VALUES (:customer_id, :name, :email, :delivery_address, :total_orders, :total_returns, :customer_type)
    """, customer_records)

    cursor.executemany("""
        INSERT INTO orders (order_id, customer_id, order_date, order_value, delivery_address, item_category, status)
        VALUES (:order_id, :customer_id, :order_date, :order_value, :delivery_address, :item_category, :status)
    """, order_records)

    return_tuples = [
        (
            r["return_id"], r["order_id"], r["customer_id"], r["request_date"],
            r["delivery_address"], r["return_address"], r["return_reason"], r["order_value"],
            r["risk_score"], r["risk_level"], r["recommendation"],
            json.dumps(r["reasons"]), json.dumps(r["breakdown"]),
            "approved" if r["recommendation"] == "auto_approve" else "pending"
        )
        for r in return_records
    ]

    cursor.executemany("""
        INSERT INTO returns (
            return_id, order_id, customer_id, request_date,
            delivery_address, return_address, return_reason, order_value,
            risk_score, risk_level, recommendation, reasons_json, breakdown_json,
            review_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, return_tuples)

    conn.commit()
    conn.close()

    summary = {
        "customers_created": len(customer_records),
        "orders_created": len(order_records),
        "returns_created": len(return_records),
        "high_risk_returns": sum(1 for r in return_records if r["risk_level"] == "high"),
        "medium_risk_returns": sum(1 for r in return_records if r["risk_level"] == "medium"),
        "low_risk_returns": sum(1 for r in return_records if r["risk_level"] == "low"),
    }

    if verbose:
        print("Data Generation Complete:")
        print(f"  Customers: {summary['customers_created']}")
        print(f"  Orders:    {summary['orders_created']}")
        print(f"  Returns:   {summary['returns_created']}")
        print(f"    - Low Risk:    {summary['low_risk_returns']}")
        print(f"    - Medium Risk: {summary['medium_risk_returns']}")
        print(f"    - High Risk:   {summary['high_risk_returns']}")

    return summary


if __name__ == "__main__":
    generate_synthetic_data()
