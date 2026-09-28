"""
FastAPI REST API for Fraud Risk Scorer

Provides endpoints for scoring returns, retrieving audit queues,
managing manual reviews, viewing rule metadata, and serving the dashboard.
"""

import os
import sys
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.scorer import score_return_request
from src.rules import ACTIVE_RULES
from src.database import (
    init_db,
    save_return,
    get_customer,
    get_customer_history,
    list_returns,
    update_return_review_status,
    get_dashboard_stats,
    DB_PATH
)
from src.generator import generate_synthetic_data

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure database is initialized on startup."""
    init_db(DB_PATH)
    yield

app = FastAPI(
    title="Return & Exchange Fraud Risk Scorer API",
    description="Automated risk scoring system for e-commerce returns and exchanges based on behavioral and policy abuse rules.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request & Response Models
# ============================================================================
class ReturnScoreRequest(BaseModel):
    customer_id: str = Field(..., description="Unique customer ID", json_schema_extra={"example": "CUST_1042"})
    order_id: Optional[str] = Field(None, description="Associated order ID", json_schema_extra={"example": "ORD_10842"})
    total_orders: Optional[int] = Field(None, ge=0, description="Lifetime total orders", json_schema_extra={"example": 14})
    total_returns: Optional[int] = Field(None, ge=0, description="Lifetime total returns", json_schema_extra={"example": 11})
    delivery_address: str = Field(..., description="Original delivery address", json_schema_extra={"example": "12 MG Road, Pune"})
    return_address: str = Field(..., description="Return pickup address", json_schema_extra={"example": "45 Park Street, Kolkata"})
    return_reason: str = Field(..., description="Reason for return", json_schema_extra={"example": "item_damaged"})
    order_value: float = Field(..., ge=0, description="Monetary value of the order", json_schema_extra={"example": 2499.0})
    days_since_delivery: Optional[int] = Field(None, ge=0, description="Days elapsed since delivery", json_schema_extra={"example": 2})
    days_since_purchase: Optional[int] = Field(None, ge=0, description="Days elapsed since order", json_schema_extra={"example": 4})
    damaged_returns_count: Optional[int] = Field(None, ge=0, description="Past damaged return claims", json_schema_extra={"example": 3})
    returns_last_7_days: Optional[int] = Field(None, ge=0, description="Returns filed in past 7 days", json_schema_extra={"example": 0})
    is_sale_period: Optional[bool] = Field(False, description="Whether order was placed during a discount sale")
    save_record: Optional[bool] = Field(True, description="Whether to persist this return audit in database")


class ReviewActionRequest(BaseModel):
    status: str = Field(..., pattern="^(approved|rejected)$", description="Review decision", json_schema_extra={"example": "approved"})


class DataGenRequest(BaseModel):
    num_customers: int = Field(500, ge=50, le=5000, description="Number of synthetic customers to generate")



@app.post("/api/score-return", summary="Score Return Request", tags=["Scoring"])
def score_return(payload: ReturnScoreRequest) -> Dict[str, Any]:
    """
    Evaluates a return request against fraud red flags and returns composite risk score,
    risk level, triggered reasons, and automated routing recommendation.
    """
    req_dict = payload.model_dump()
    cust_id = payload.customer_id

    # If historical metrics were not provided in payload, look up customer profile in SQLite
    if payload.total_orders is None or payload.total_returns is None:
        history = get_customer_history(cust_id)
        if history and history.get("total_orders", 0) > 0:
            if req_dict.get("total_orders") is None:
                req_dict["total_orders"] = history["total_orders"]
            if req_dict.get("total_returns") is None:
                req_dict["total_returns"] = history["total_returns"]
            if req_dict.get("damaged_returns_count") is None:
                req_dict["damaged_returns_count"] = history["damaged_returns_count"]
            if req_dict.get("returns_last_7_days") is None:
                req_dict["returns_last_7_days"] = history["returns_last_7_days"]

    # Compute risk score
    result = score_return_request(req_dict)

    # Optionally persist evaluated return into database
    if payload.save_record:
        ret_id = f"RET_{uuid.uuid4().hex[:8].upper()}"
        ord_id = payload.order_id or f"ORD_{uuid.uuid4().hex[:6].upper()}"
        now_str = datetime.now(timezone.utc).isoformat()

        record = {
            "return_id": ret_id,
            "order_id": ord_id,
            "customer_id": cust_id,
            "request_date": now_str,
            "delivery_address": payload.delivery_address,
            "return_address": payload.return_address,
            "return_reason": payload.return_reason,
            "order_value": payload.order_value,
            "risk_score": result["risk_score"],
            "risk_level": result["risk_level"],
            "recommendation": result["recommendation"],
            "reasons": result["reasons"],
            "breakdown": result["breakdown"]
        }
        save_return(record)
        result["return_id"] = ret_id
        result["order_id"] = ord_id

    return result


@app.get("/api/returns", summary="List Returns", tags=["Returns Audit Queue"])
def get_returns(
    risk_level: Optional[str] = Query("all", description="Filter by risk level ('all', 'low', 'medium', 'high')"),
    search: Optional[str] = Query(None, description="Search term for customer_id, return_id, or order_id"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Retrieve scored return records with filtering and pagination."""
    items = list_returns(risk_level=risk_level, limit=limit, offset=offset, search=search)
    return {"count": len(items), "returns": items}


@app.post("/api/returns/{return_id}/review", summary="Review Flagged Return", tags=["Manual Review"])
def review_return(return_id: str, payload: ReviewActionRequest):
    """Update human review status for a flagged return request."""
    success = update_return_review_status(return_id, payload.status)
    if not success:
        raise HTTPException(status_code=404, detail="Return ID not found")
    return {"message": f"Return {return_id} marked as {payload.status}", "status": payload.status}


@app.get("/api/stats", summary="Get Dashboard Stats", tags=["Analytics"])
def get_stats():
    """Retrieve aggregate statistics on return volume, risk distributions, and values."""
    return get_dashboard_stats()


@app.get("/api/rules", summary="List Configured Fraud Rules", tags=["Rules Configuration"])
def get_rules():
    """List all active fraud detection rules, explanations, and assigned point weights."""
    return [
        {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "points": rule.max_points,
            "category": getattr(rule, "category", "general"),
            "explanation": rule.explanation
        }
        for rule in ACTIVE_RULES
    ]


@app.get("/api/customers/{customer_id}", summary="Get Customer Profile", tags=["Customers"])
def get_customer_profile(customer_id: str):
    """Get customer transaction history and return behavior summary."""
    cust = get_customer(customer_id)
    if not cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    history = get_customer_history(customer_id)
    return {**cust, **history}


@app.post("/api/generate-data", summary="Regenerate Synthetic Data", tags=["Synthetic Data"])
def regenerate_data(payload: DataGenRequest):
    """Re-seed the SQLite database with new synthetic customers and returns."""
    summary = generate_synthetic_data(num_customers=payload.num_customers, verbose=False)
    return {"message": "Synthetic dataset successfully generated", "summary": summary}


# ============================================================================
# Static Files & Dashboard Mount
# ============================================================================
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
def serve_dashboard():
    """Serve modern single-page dashboard."""
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Fraud Risk Scorer API is running. Visit /docs for Swagger API documentation."}
