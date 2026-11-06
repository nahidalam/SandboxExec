from verifier import verify_artifact


def test_verifier_confirms_aggregate_data_only():
    payload = {
        "enterprise": 820000,
        "mid_market": 410000,
        "small_business": 170000,
    }
    agreement = {
        "resource": "revenue_by_segment.json",
        "purpose": "revenue_report",
        "status": "approved",
    }
    result = verify_artifact(payload, agreement)
    assert result["verified"] is True
    assert result["schema_valid"] is True
    assert result["contains_customer_identifiers"] is False
    assert result["agreement_satisfied"] is True
