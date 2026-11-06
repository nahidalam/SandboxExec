def create_agreement(
    requester: str,
    provider: str,
    resource: str,
    operation: str,
    purpose: str,
    scope: str = "current_task",
    status: str = "approved",
):
    return {
        "requester": requester,
        "provider": provider,
        "resource": resource,
        "operation": operation,
        "purpose": purpose,
        "scope": scope,
        "status": status,
    }


def validate_agreement(agreement):
    required = {
        "requester": "agent_b",
        "provider": "agent_a",
        "resource": "revenue_by_segment.json",
        "operation": "read",
        "purpose": "revenue_report",
        "scope": "current_task",
        "status": "approved",
    }

    valid = all(agreement.get(key) == value for key, value in required.items())
    return {
        "valid": valid,
        "agreement": agreement,
        "required": required,
    }
