"""
Fraud Risk Scorer CLI Runner

Convenient CLI runner for data generation, server startup, test execution, and demo scoring.
"""

import sys
import os
import argparse
import json

# Ensure project root is in path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database import DB_PATH, init_db
from src.generator import generate_synthetic_data
from src.scorer import score_return_request


def run_generate(num_customers: int = 1200):
    print("=" * 60)
    print("Generating Synthetic E-Commerce Dataset...")
    print("=" * 60)
    summary = generate_synthetic_data(num_customers=num_customers)
    print("\nDataset ready in SQLite database: data/store.db")
    return summary


def run_demo():
    print("=" * 70)
    print("SentinelRisk Fraud Risk Scorer - Terminal Demonstration")
    print("=" * 70)

    # Scenario A: Genuine Customer Return
    genuine_payload = {
        "customer_id": "CUST_1008",
        "total_orders": 12,
        "total_returns": 1,
        "delivery_address": "88 Brigade Road, Bengaluru",
        "return_address": "88 Brigade Road, Bengaluru",
        "return_reason": "wrong_size",
        "order_value": 1199.0,
        "days_since_delivery": 6
    }
    print("\n[SCENARIO A] Evaluating Genuine Customer Return Request:")
    print(json.dumps(genuine_payload, indent=2))
    verdict_a = score_return_request(genuine_payload)
    print(f"\n>> Verdict: Risk Score {verdict_a['risk_score']}/100 [{verdict_a['risk_level'].upper()}]")
    print(f">> Recommendation: {verdict_a['recommendation']}")
    print(f">> Triggered Rules: {verdict_a['reasons'] or 'None (Clean)'}")

    # Scenario B: High Risk Abuse (Example from project brief)
    brief_payload = {
        "customer_id": "CUST_1042",
        "total_orders": 14,
        "total_returns": 11,
        "delivery_address": "12 MG Road, Pune",
        "return_address": "45 Park Street, Kolkata",
        "return_reason": "item_damaged",
        "order_value": 2499.0
    }
    print("\n" + "-" * 70)
    print("\n[SCENARIO B] Evaluating High-Risk Return (Project Brief Example):")
    print(json.dumps(brief_payload, indent=2))
    verdict_b = score_return_request(brief_payload)
    print(f"\n>> Verdict: Risk Score {verdict_b['risk_score']}/100 [{verdict_b['risk_level'].upper()}]")
    print(f">> Recommendation: {verdict_b['recommendation']}")
    print(f">> Triggered Rules: {verdict_b['reasons']}")
    for r in verdict_b['breakdown']:
        print(f"    - {r['name']} (+{r['points']} pts): {r['reason']}")

    print("\n" + "=" * 70)


def run_tests():
    import pytest
    print("=" * 60)
    print("Running Pytest Test Suite...")
    print("=" * 60)
    sys.exit(pytest.main(["-v", "tests"]))


def run_serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    import uvicorn
    # Check if database exists, generate if missing
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        print("Database not found. Seeding initial synthetic data...")
        generate_synthetic_data(num_customers=800, verbose=False)

    print("=" * 70)
    print(f"Starting SentinelRisk Server on http://{host}:{port}")
    print(f"  - Web Dashboard:     http://{host}:{port}/")
    print(f"  - Interactive API:   http://{host}:{port}/docs")
    print("=" * 70)
    uvicorn.run("src.api:app", host=host, port=port, reload=reload)


def main():
    parser = argparse.ArgumentParser(description="SentinelRisk Fraud Risk Scorer")
    parser.add_argument("command", nargs="?", default="serve", choices=["serve", "generate", "demo", "test"],
                        help="Command to run (default: serve)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind server (default: 8000)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--customers", type=int, default=1200, help="Number of customers to generate")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    if args.command == "generate":
        run_generate(num_customers=args.customers)
    elif args.command == "demo":
        run_demo()
    elif args.command == "test":
        run_tests()
    elif args.command == "serve":
        run_serve(host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
