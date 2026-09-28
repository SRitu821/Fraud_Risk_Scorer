"""
SQLite Database Layer for Fraud Risk Scorer

Handles persistence of synthetic customers, orders, returns, and scoring audits.
"""

import sqlite3
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "store.db")


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Create and return a database connection with row factory."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize database tables and indexes."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            delivery_address TEXT NOT NULL,
            total_orders INTEGER DEFAULT 0,
            total_returns INTEGER DEFAULT 0,
            customer_type TEXT DEFAULT 'normal',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            order_date TIMESTAMP NOT NULL,
            order_value REAL NOT NULL,
            delivery_address TEXT NOT NULL,
            item_category TEXT NOT NULL,
            status TEXT DEFAULT 'delivered',
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS returns (
            return_id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            request_date TIMESTAMP NOT NULL,
            delivery_address TEXT NOT NULL,
            return_address TEXT NOT NULL,
            return_reason TEXT NOT NULL,
            order_value REAL NOT NULL,
            risk_score INTEGER NOT NULL,
            risk_level TEXT NOT NULL,
            recommendation TEXT NOT NULL,
            reasons_json TEXT NOT NULL,
            breakdown_json TEXT NOT NULL,
            review_status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE INDEX IF NOT EXISTS idx_returns_risk_level ON returns(risk_level);
        CREATE INDEX IF NOT EXISTS idx_returns_customer_id ON returns(customer_id);
        CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
    """)

    conn.commit()
    conn.close()


def save_customer(customer: Dict[str, Any], db_path: str = DB_PATH) -> None:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO customers 
        (customer_id, name, email, delivery_address, total_orders, total_returns, customer_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        customer["customer_id"],
        customer["name"],
        customer["email"],
        customer["delivery_address"],
        customer.get("total_orders", 0),
        customer.get("total_returns", 0),
        customer.get("customer_type", "normal")
    ))
    conn.commit()
    conn.close()


def save_return(return_record: Dict[str, Any], db_path: str = DB_PATH) -> str:
    """Save an evaluated return record to the database."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    reasons_json = json.dumps(return_record.get("reasons", []))
    breakdown_json = json.dumps(return_record.get("breakdown", []))
    review_status = "approved" if return_record.get("recommendation") == "auto_approve" else "pending"

    cursor.execute("""
        INSERT OR REPLACE INTO returns (
            return_id, order_id, customer_id, request_date,
            delivery_address, return_address, return_reason, order_value,
            risk_score, risk_level, recommendation, reasons_json, breakdown_json,
            review_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        return_record["return_id"],
        return_record.get("order_id", f"ORD_{return_record['return_id']}"),
        return_record["customer_id"],
        return_record.get("request_date", datetime.now(timezone.utc).isoformat()),
        return_record.get("delivery_address", ""),

        return_record.get("return_address", ""),
        return_record.get("return_reason", "changed_mind"),
        float(return_record.get("order_value", 0.0)),
        int(return_record.get("risk_score", 0)),
        return_record.get("risk_level", "low"),
        return_record.get("recommendation", "auto_approve"),
        reasons_json,
        breakdown_json,
        review_status
    ))

    # Also increment customer returns if customer exists
    cursor.execute("""
        UPDATE customers 
        SET total_returns = total_returns + 1 
        WHERE customer_id = ?
    """, (return_record["customer_id"],))

    conn.commit()
    conn.close()
    return return_record["return_id"]


def get_customer(customer_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_customer_history(customer_id: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Retrieve full behavioral profile for scoring a return request."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    cust = cursor.fetchone()

    cursor.execute("""
        SELECT return_reason, request_date 
        FROM returns 
        WHERE customer_id = ?
        ORDER BY request_date DESC
    """, (customer_id,))
    past_returns = [dict(r) for r in cursor.fetchall()]

    conn.close()

    if not cust:
        return {
            "customer_id": customer_id,
            "total_orders": 0,
            "total_returns": 0,
            "delivery_address": "",
            "damaged_returns_count": 0,
            "returns_last_7_days": 0
        }

    damaged_count = sum(1 for r in past_returns if r.get("return_reason") == "item_damaged")
    
    # Calculate returns in last 7 days from records
    now = datetime.utcnow()
    recent_count = 0
    for r in past_returns:
        try:
            r_date = datetime.fromisoformat(r["request_date"])
            if (now - r_date).days <= 7:
                recent_count += 1
        except Exception:
            pass

    return {
        "customer_id": cust["customer_id"],
        "name": cust["name"],
        "delivery_address": cust["delivery_address"],
        "total_orders": cust["total_orders"],
        "total_returns": cust["total_returns"],
        "damaged_returns_count": damaged_count,
        "returns_last_7_days": recent_count,
        "customer_type": cust["customer_type"]
    }


def list_returns(
    risk_level: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
    db_path: str = DB_PATH
) -> List[Dict[str, Any]]:
    """List return records with filtering and pagination."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = "SELECT * FROM returns WHERE 1=1"
    params: List[Any] = []

    if risk_level and risk_level.lower() != "all":
        query += " AND risk_level = ?"
        params.append(risk_level.lower())

    if search:
        query += " AND (customer_id LIKE ? OR return_id LIKE ? OR order_id LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = []
    for r in rows:
        d = dict(r)
        d["reasons"] = json.loads(d["reasons_json"]) if d["reasons_json"] else []
        d["breakdown"] = json.loads(d["breakdown_json"]) if d["breakdown_json"] else []
        results.append(d)

    return results


def update_return_review_status(return_id: str, new_status: str, db_path: str = DB_PATH) -> bool:
    """Update human review status ('approved', 'rejected')."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE returns SET review_status = ? WHERE return_id = ?", (new_status, return_id))
    affected = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return affected


def get_dashboard_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    """Compute aggregate risk stats for the dashboard."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            COUNT(*) as total_returns,
            SUM(CASE WHEN risk_level = 'low' THEN 1 ELSE 0 END) as low_risk_count,
            SUM(CASE WHEN risk_level = 'medium' THEN 1 ELSE 0 END) as medium_risk_count,
            SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) as high_risk_count,
            SUM(order_value) as total_return_value,
            SUM(CASE WHEN risk_level = 'high' THEN order_value ELSE 0 END) as high_risk_value,
            SUM(CASE WHEN review_status = 'pending' AND risk_level = 'high' THEN 1 ELSE 0 END) as pending_high_reviews,
            AVG(risk_score) as avg_risk_score
        FROM returns
    """)
    row = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) FROM customers")
    customer_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]

    conn.close()

    total_returns = row["total_returns"] or 0
    high_count = row["high_risk_count"] or 0
    high_rate = round((high_count / total_returns * 100), 1) if total_returns > 0 else 0

    return {
        "total_returns": total_returns,
        "total_customers": customer_count,
        "total_orders": order_count,
        "low_risk_count": row["low_risk_count"] or 0,
        "medium_risk_count": row["medium_risk_count"] or 0,
        "high_risk_count": high_count,
        "high_risk_pct": high_rate,
        "total_return_value": round(row["total_return_value"] or 0.0, 2),
        "high_risk_value_protected": round(row["high_risk_value"] or 0.0, 2),
        "pending_high_reviews": row["pending_high_reviews"] or 0,
        "avg_risk_score": round(row["avg_risk_score"] or 0.0, 1),
    }
