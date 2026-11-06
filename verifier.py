def verify_artifact(payload, agreement):
    if not isinstance(payload, dict):
        return {
            "verified": False,
            "schema_valid": False,
            "contains_customer_identifiers": True,
            "agreement_satisfied": False,
            "details": ["artifact is not a JSON object"],
        }

    allowed_keys = {"enterprise", "mid_market", "small_business"}
    schema_valid = all(isinstance(value, (int, float)) for value in payload.values()) and set(payload.keys()) <= allowed_keys

    def looks_like_customer_identifier(key, value):
        key_text = str(key).lower()
        value_text = str(value).lower() if isinstance(value, str) else ""
        return (
            "customer" in key_text
            or "customer" in value_text
            or key_text.endswith("_id")
            or key_text.startswith("customer_")
            or key_text.startswith("user_")
            or "user_id" in key_text
            or "customer_id" in key_text
        )

    contains_customer_identifiers = any(
        looks_like_customer_identifier(key, value)
        for key, value in payload.items()
    )

    agreement_satisfied = (
        agreement.get('resource') == 'revenue_by_segment.json'
        and agreement.get('purpose') == 'revenue_report'
        and agreement.get('status') == 'approved'
    )

    verified = schema_valid and not contains_customer_identifiers and agreement_satisfied
    return {
        "verified": verified,
        "schema_valid": schema_valid,
        "contains_customer_identifiers": contains_customer_identifiers,
        "agreement_satisfied": agreement_satisfied,
    }
