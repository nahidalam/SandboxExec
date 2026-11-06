from policies import evaluate_policy


def test_original_customer_record_request_is_denied():
    result = evaluate_policy("Customer-level records and revenue data.")
    assert result["status"] == "denied"
    assert result["reason"] == "customer_level_records_restricted"
    assert "revenue_by_customer_segment" in result["allowed_alternatives"]


def test_structured_feedback_contains_allowed_aggregate_alternative():
    result = evaluate_policy("Customer-level records and revenue data.")
    assert result["allowed_alternatives"] == ["revenue_by_customer_segment"]
