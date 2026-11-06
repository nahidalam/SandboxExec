from pathlib import Path

from fastapi.testclient import TestClient

from agreements import validate_agreement
from app import app, run_demo
from inference import MockProvider
from policies import evaluate_policy
from sandbox import Sandbox
from verifier import verify_artifact


def test_backend_request_policy_replan_agreement_and_verification():
    provider = MockProvider()
    result = run_demo()

    assert result["request"]["original"] == provider.get_initial_request()

    denial = evaluate_policy(result["request"]["original"])
    assert denial["status"] == "denied"
    assert denial["reason"] == "customer_level_records_restricted"
    assert denial == result["denial"]

    assert result["request"]["replanned"] == provider.get_replanned_request(denial)
    assert result["agreement_validation"]["valid"] is True
    assert validate_agreement(result["agreement"])["valid"] is True
    assert result["verification"]["verified"] is True
    assert result["execution"]["agent_a"]["exit_code"] == 0
    assert result["execution"]["agent_b"]["exit_code"] == 0
    assert result["execution"]["agent_a"]["cleanup_done"] is True
    assert result["execution"]["agent_b"]["cleanup_done"] is True
    assert result["security"]["agent_b_received_customers_csv"] is False
    assert result["security"]["agent_b_received_only_approved_artifact"] is True
    assert result["execution"]["final_report_generated"] is True


def test_agent_a_and_agent_b_use_real_docker_and_customer_data_stays_isolated():
    root = Path(__file__).resolve().parents[1]
    customers_path = root / "data" / "customers.csv"
    agent_a = Sandbox("agent_a_real", workdir=str(root / "tmp" / "agent_a_real"))
    agent_a_result = agent_a.run_python(
        "from pathlib import Path; p = Path('/workspace/customers.csv'); print('present' if p.exists() else 'missing'); print(p.read_text().splitlines()[0])",
        files=[(str(customers_path), '/workspace/customers.csv')],
        output_dir=str(root / "data" / "agent_a"),
    )
    assert agent_a_result["exit_code"] == 0
    assert "present" in agent_a_result["stdout"].lower()
    assert "customer_id" in agent_a_result["stdout"].lower()

    artifact_path = root / "data" / "agent_a" / "revenue_by_segment.json"
    assert artifact_path.exists()

    agent_b = Sandbox("agent_b_real", workdir=str(root / "tmp" / "agent_b_real"))
    agent_b_result = agent_b.run_python(
        "from pathlib import Path; p = Path('/workspace/customers.csv'); print('present' if p.exists() else 'not_available')",
        files=[(str(artifact_path), '/workspace/revenue_by_segment.json')],
        output_dir=str(root / "data" / "agent_b"),
    )
    assert agent_a.workdir != agent_b.workdir
    assert "not_available" in agent_b_result["stdout"].lower()
    assert agent_b_result["exit_code"] == 0

    payload = {
        "enterprise": 620000,
        "mid_market": 410000,
        "small_business": 170000,
    }
    agreement = {
        "resource": "revenue_by_segment.json",
        "purpose": "revenue_report",
        "status": "approved",
    }
    verification = verify_artifact(payload, agreement)
    assert verification["verified"] is True
    assert verification["contains_customer_identifiers"] is False


def test_view_report_route_serves_generated_html():
    run_demo()
    client = TestClient(app)
    response = client.get("/api/report")

    assert response.status_code == 200
    assert "Revenue Report" in response.text
    assert "Enterprise" in response.text
    assert "Mid-market" in response.text
    assert "Small business" in response.text
