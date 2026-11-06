def evaluate_policy(request_text: str):
    request = (request_text or "").strip().lower()

    if "customer-level" in request or "customer level" in request or "customer_id" in request or "customer records" in request:
        return {
            "status": "denied",
            "reason": "customer_level_records_restricted",
            "allowed_alternatives": ["revenue_by_customer_segment"],
        }

    if "revenue" in request or "segment" in request:
        return {
            "status": "approved",
            "reason": "aggregate_revenue_request_allowed",
            "allowed_alternatives": ["revenue_by_customer_segment"],
        }

    return {
        "status": "approved",
        "reason": "safe_request_allowed",
        "allowed_alternatives": ["revenue_by_customer_segment"],
    }
