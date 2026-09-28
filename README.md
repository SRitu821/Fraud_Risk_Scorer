# SentinelRisk: Product Return & Exchange Fraud Risk Scorer

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Pytest](https://img.shields.io/badge/tests-22%20passed-success.svg)](https://docs.pytest.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> An automated, explainable risk-scoring decision engine and fraud operations review dashboard for e-commerce return and exchange requests. Evaluates behavioral anomalies, policy abuse patterns, and velocity spikes to instantly approve genuine returns while routing high-risk requests to fraud analysts.

---

## 📌 Problem & Business Context

In modern e-commerce, customer-friendly return policies (free returns, instant refunds, no-questions-asked replacements) are critical for customer acquisition. However, they also create a multi-billion dollar vector for abuse:

- **Serial Returners / Bracketing**: Ordering high volumes of items and habitually returning 75%+ of everything ordered.
- **Wardrobing / "Tag-Tucking"**: Purchasing expensive items (formal wear, designer apparel, premium electronics), using them for a one-time event or social media shoot, and returning them within 48–72 hours for a full refund.
- **Chronic Damage Claims**: Exploiting "item arrived broken/damaged" policies to obtain refunds or free replacements without returning the original item.
- **Address Interception / Refund Diversion**: Ordering merchandise to one delivery address and redirecting pickup or refund destination to an unrelated city.

Treating every return request identically causes companies to bleed operating margin on shipping and unsellable inventory. **SentinelRisk** scores every return request from `0` to `100`, providing instant automated approvals for honest shoppers and actionable evidence dossiers for suspicious ones.

---

## 🏗️ Architecture & Decision Pipeline

```
              ┌──────────────────────────────────────────────┐
              │  E-Commerce Platform / Customer Return Req   │
              └───────────────────────┬──────────────────────┘
                                      │  POST /api/score-return
                                      ▼
                        ┌───────────────────────────┐
                        │    FastAPI REST Server    │
                        └─────────────┬─────────────┘
                                      │
            ┌─────────────────────────┴─────────────────────────┐
            ▼                                                   ▼
┌───────────────────────┐                           ┌───────────────────────┐
│ SQLite Database Store │                           │  Fraud Rules Engine   │
│  - Customers Profile  │                           │  - Velocity Checks    │
│  - Orders History     │◄─────────────────────────►│  - Address Geography  │
│  - Past Returns Log   │                           │  - Defect Claims Rate │
└───────────────────────┘                           │  - Wardrobing Window  │
                                                    └───────────┬───────────┘
                                                                │
                                                                ▼
                                                    ┌───────────────────────┐
                                                    │ Composite Risk Scorer │
                                                    │ Score: 0 - 100        │
                                                    │ Tiers: Low / Med / High│
                                                    └───────────┬───────────┘
                                                                │
                                     ┌──────────────────────────┴──────────────────────────┐
                                     ▼                                                     ▼
                         [Score <= 30: LOW RISK]                              [Score >= 61: HIGH RISK]
                         Auto-Approve                                         Route to Manual Review
                         - Instant Return Label                               - CCTV Inspection on Dock
                         - Instant Refund Issued                              - Audit Queue in SentinelRisk UI
```

---

## ⚖️ Fraud Rules Engine & Point System

Each rule represents an established retail risk pattern with calibrated point values and human-readable explainability:

| Rule ID | Rule Name | Category | Max Points | Trigger Condition & Domain Rationale |
| :--- | :--- | :--- | :---: | :--- |
| `return_rate_too_high` | **Extreme Return Rate** | Behavioral | **47 pts** | Customer lifetime return rate $\ge 70\%$ across $\ge 5$ orders. Normal retail returns sit at 5%–15%. Sustained rates above 70% indicate policy abuse. Scales from 35 to 47 pts for severe rates ($\ge 78\%$). |
| `moderate_return_rate` | **Elevated Return Rate** | Behavioral | **15 pts** | Return rate between 50% and 70% across $\ge 4$ orders. Early warning tier for elevated return behavior. |
| `address_mismatch` | **Address Mismatch** | Geographic | **35 pts** | Delivery city and return pickup/refund address belong to distinct geographic regions (e.g., delivered to Pune, return requested from Kolkata). High indicator of intercepted packages or refund fraud. |
| `chronic_damaged_claims` | **Repetitive Damaged Claims** | Policy Abuse | **25 pts** | Customer repeatedly files "item damaged" returns ($\ge 2$ prior damaged returns and current reason is damaged, or $\ge 70\%$ lifetime damaged claims). Courier transit damage is statistically rare ($<3\%$). |
| `sudden_return_spike` | **Sudden Return Spike** | Velocity | **25 pts** | Customer files $\ge 3$ return requests within a 7-day period. Velocity bursts indicate liquidation abuse or account compromise. |
| `wardrobing_pattern` | **Wardrobing / Rapid Luxury** | Retail Fraud | **25 pts** | High-value order ($\ge ₹2,000$) returned within 72 hours of delivery citing discretionary remorse ("changed mind", "wrong size"). Matches the signature of single-use event wear. |
| `new_customer_high_value` | **New Customer High-Value** | Account Age | **20 pts** | First-time or new customer account ($\le 1$ prior order) filing a return on an expensive item ($\ge ₹2,500$) without an established trust baseline. |

### Operational Risk Tiers & Actions

- **`0 – 30` | Low Risk (`auto_approve`)**: Seamless customer experience. Instant prepaid shipping label issued and refund automated upon first courier carrier scan.
- **`31 – 60` | Medium Risk (`light_review`)**: Automated secondary verification. Customer is prompted in the app to upload photo proof of item tags, condition, or packaging prior to shipping authorization.
- **`61 – 100` | High Risk (`route_to_manual_review`)**: Routed to human fraud operations. Refund held until physical inspection under warehouse CCTV is completed.

---

## 💻 Tech Stack

- **Python 3.10+**: Core programming language.
- **FastAPI**: Asynchronous high-performance REST API.
- **Pydantic V2**: Strongly-typed request/response validation and schemas.
- **SQLite**: Local relational database persisting customers, orders, returns, and audit decisions.
- **Pandas / NumPy**: Dataset synthesis and distribution modeling.
- **Pytest**: Automated test suite with 100% rule and edge-case coverage.
- **Vanilla CSS (Glassmorphism) & JavaScript**: Modern, responsive dark-mode dashboard with real-time SVG circular gauge animations.

---

## 🚀 Quick Start Guide

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/Fraud_Risk_Scorer.git
cd Fraud_Risk_Scorer

# Install dependencies
pip install -r requirements.txt
```

### 2. Run Terminal Demonstration

Run the built-in CLI demo comparing a genuine customer against the project brief's high-risk sample:

```bash
python run.py demo
```

Output:
```text
[SCENARIO A] Evaluating Genuine Customer Return Request:
>> Verdict: Risk Score 0/100 [LOW]
>> Recommendation: auto_approve
>> Triggered Rules: None (Clean)

[SCENARIO B] Evaluating High-Risk Return (Project Brief Example):
>> Verdict: Risk Score 82/100 [HIGH]
>> Recommendation: route_to_manual_review
>> Triggered Rules: ['return_rate_too_high', 'address_mismatch']
    - Extreme Return Rate (>70%) (+47 pts): Return rate is 78.6% across 14 orders
    - Address Mismatch (+35 pts): Delivery address ('12 MG Road, Pune') mismatches return pickup ('45 Park Street, Kolkata')
```

### 3. Launch Server & Web Dashboard

Start the application:

```bash
python run.py serve
```

Open your browser:
- **Interactive Review Dashboard**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Swagger REST API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Run Automated Test Suite

```bash
python run.py test
# or
python -m pytest -v
```

---

## 📡 REST API Reference

### Evaluate Return Request

**`POST /api/score-return`**

#### High-Risk Request Example (Project Brief):
```json
{
  "customer_id": "CUST_1042",
  "total_orders": 14,
  "total_returns": 11,
  "delivery_address": "12 MG Road, Pune",
  "return_address": "45 Park Street, Kolkata",
  "return_reason": "item_damaged",
  "order_value": 2499.0
}
```

#### High-Risk Response:
```json
{
  "customer_id": "CUST_1042",
  "risk_score": 82,
  "risk_level": "high",
  "reasons": [
    "return_rate_too_high",
    "address_mismatch"
  ],
  "recommendation": "route_to_manual_review",
  "breakdown": [
    {
      "rule_id": "return_rate_too_high",
      "name": "Extreme Return Rate (>70%)",
      "triggered": true,
      "points": 47,
      "max_points": 47,
      "reason": "Return rate is 78.6% across 14 orders (threshold: 70%, min 5 orders)",
      "explanation": "Customer has returned over 70% of total lifetime purchases...",
      "metadata": { "rate": 0.7857, "rate_pct": 78.6, "total_orders": 14, "total_returns": 11 }
    },
    {
      "rule_id": "address_mismatch",
      "name": "Address Mismatch",
      "triggered": true,
      "points": 35,
      "max_points": 35,
      "reason": "Delivery address ('12 MG Road, Pune') mismatches return pickup ('45 Park Street, Kolkata')",
      "explanation": "Item was delivered to one address, but refund/pickup is requested from an unrelated address...",
      "metadata": { "delivery_address": "12 MG Road, Pune", "return_address": "45 Park Street, Kolkata" }
    }
  ],
  "total_rules_evaluated": 7,
  "triggered_count": 2,
  "return_id": "RET_60C034AB",
  "order_id": "ORD_E1DFBB"
}
```

#### Low-Risk Request Example:
```json
{
  "customer_id": "CUST_GENUINE",
  "total_orders": 10,
  "total_returns": 1,
  "delivery_address": "88 Brigade Road, Bengaluru",
  "return_address": "88 Brigade Road, Bengaluru",
  "return_reason": "wrong_size",
  "order_value": 999.0
}
```

#### Low-Risk Response:
```json
{
  "customer_id": "CUST_GENUINE",
  "risk_score": 0,
  "risk_level": "low",
  "reasons": [],
  "recommendation": "auto_approve",
  "breakdown": [],
  "total_rules_evaluated": 7,
  "triggered_count": 0,
  "return_id": "RET_81B099FC",
  "order_id": "ORD_419B62"
}
```

---

## 🖥️ Review Dashboard Features

The SentinelRisk web portal (`http://127.0.0.1:8000/`) includes:

1. **Executive Metric Cards**: Real-time totals for evaluated return volume, auto-approval percentage, protected fraud value, and pending manual reviews.
2. **Interactive Live Scoring Sandbox**:
   - Customizable return request parameters (customer order history, addresses, timing, item values, sale flags).
   - **One-Click Real-World Presets**: Test "Genuine Shopper", "Serial Returner", "Address Interception", "Chronic Damaged Claims", "Wardrobing", and "Brand New Account".
   - **SVG Score Gauge & Explainability Breakdown**: Visual circular gauge dynamically color-coded with point-by-point rule breakdowns.
3. **Fraud Operations Review Queue**:
   - Filter returns by status (`All`, `High Risk`, `Medium Risk`, `Low Risk`).
   - Search by Customer ID, Return ID, or Order ID.
   - **Dossier Inspection Modal**: Deep-dive into customer order history and click **"Approve Return"** or **"Reject & Flag"** with instant database state updates.
4. **Rules Matrix Explorer**: Visual catalog of all active fraud rules, categories, and business logic.
5. **Synthetic Data Controller**: "Regenerate Data" button to simulate thousands of fresh transactions on demand.

---

## 🎯 Interview Talking Points & Technical Rationale

When discussing this project in a system design, fintech, or data engineering interview, highlight these key design principles:

### 1. The Core Trade-Off: False Positives vs. False Negatives
- **False Positives (Type I Error)**: Flagging an honest customer as fraudulent.
  - *Business Impact*: Insults high-value customers, adds customer support tickets, and destroys brand loyalty. A loyal shopper who spends $5,000/year might churn forever if subjected to an aggressive fraud check over a $40 shirt.
  - *Mitigation in SentinelRisk*: We set `0–30` as a generous safe zone, require a minimum sample size of 5 orders before applying return rate penalties, and use a tiered `light_review` for borderline cases.
- **False Negatives (Type II Error)**: Approving an abusive return.
  - *Business Impact*: Inventory loss, unpaid shipping fees, and exploitation by organized retail crime rings.
  - *Mitigation in SentinelRisk*: Severe compound violations (e.g. cross-city address redirection + high return rate) immediately score $\ge 80$, ensuring high-confidence fraud is intercepted before refund disbursement.

### 2. Explainability Over Black-Box Models
- In regulated commerce and financial systems, **explainability is mandatory**. Customer support agents and fraud analysts must be able to justify why a refund was held.
- SentinelRisk's rule breakdown outputs human-readable explanations and metadata rather than an opaque float, empowering human analysts during manual review.

### 3. Generalizability Beyond E-Commerce Returns
The exact same architectural pattern applies directly across multiple domains:
- **Payment & Card Fraud**: Sudden velocity spikes, billing vs. shipping address discrepancies, card-testing patterns.
- **Account Takeover (ATO)**: Dormant accounts suddenly ordering high-ticket electronics with address alterations.
- **Promotion & Coupon Abuse**: Disposable accounts using referral codes across identical device fingerprints or IP subnets.

---

## 📁 Repository Structure

```
Fraud_Risk_Scorer/
│
├── data/
│   └── store.db                   # SQLite database (customers, orders, returns)
│
├── src/
│   ├── __init__.py                # Package root
│   ├── rules.py                   # Rule definitions, point weights, and explainability
│   ├── scorer.py                  # Core scoring engine, composite score, risk levels
│   ├── generator.py               # Synthetic dataset generator with 6 fraud archetypes
│   ├── database.py                # SQLite repository, schema, queries, review actions
│   └── api.py                     # FastAPI application serving REST endpoints and UI
│
├── static/                        # Glassmorphism Dashboard UI
│   ├── index.html                 # Single-page interface
│   ├── style.css                  # Dark design system, tokens, SVG gauges, animations
│   └── app.js                     # Interactive sandbox, presets, queue table, modal
│
├── tests/
│   ├── __init__.py
│   ├── test_rules.py              # Unit tests for each individual detection rule
│   ├── test_scorer.py             # Scorer edge cases, capping, and boundaries
│   └── test_api.py                # REST API endpoint integration tests
│
├── run.py                         # Unified CLI runner (serve, demo, generate, test)
├── requirements.txt               # Project dependencies
└── README.md                      # Comprehensive project documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
