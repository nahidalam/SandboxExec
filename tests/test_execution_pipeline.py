from pathlib import Path

from fastapi.testclient import TestClient

from agreements import validate_agreement
from app import app, run_demo
from inference import MockProvider
from policies import evaluate_policy
from sandbox import Sandbox


class BrokenAgentA(MockProvider):
    def get_agent_a_code(self):
        return "raise RuntimeError('intentional failure')"


class MissingArtifact(MockProvider):
    def get_agent_a_code(self):
        return "print('ran without creating artifact')"


class BrokenAgentB(MockProvider):
    def get_report_code(self):
        return "raise RuntimeError('intentional failure')"


def test_backend_workflow_uses_real_docker_and_verified_artifact():
    result = run_demo(MockProvider())
    assert result['status'] == 'complete'
    assert result['audit']['timeline'] == ['REQUEST', 'DENIED', 'REPLAN', 'AGREEMENT', 'EXECUTE', 'VERIFY', 'COMPLETE']
    assert result['denial']['status'] == 'denied'
    assert result['denial']['allowed_alternatives'] == ['revenue_by_customer_segment']
    assert result['replan_policy']['status'] == 'approved'
    assert evaluate_policy(result['request']['replanned'])['status'] == 'approved'
    assert validate_agreement(result['agreement'])['valid']
    assert result['agreement_validation']['valid']
    assert result['verification']['verified']
    assert result['artifact'] == {'enterprise': 620000, 'mid_market': 410000, 'small_business': 170000}
    assert (Path(__file__).resolve().parents[1] / 'data/agent_a/revenue_by_segment.json').is_file()
    a = result['execution']['agent_a']
    b = result['execution']['agent_b']
    assert a['exit_code'] == b['exit_code'] == 0
    assert a['sandbox_id'] != b['sandbox_id']
    assert a['stdout'] and b['stdout']
    assert a['docker_image'] == b['docker_image'] == 'python:3.12-slim'
    assert a['duration_seconds'] > 0 and b['duration_seconds'] > 0
    assert a['network_disabled'] and b['network_disabled']
    assert a['cpu_limit'] == b['cpu_limit'] == '0.5 CPU'
    assert a['memory_limit'] == b['memory_limit'] == '256m'
    assert a['pid_limit'] == b['pid_limit'] == 64
    assert a['customers_csv'] == 'MOUNTED READ-ONLY'
    assert b['customers_csv'] == 'NOT MOUNTED'
    assert b['revenue_by_segment_json'] == 'MOUNTED READ-ONLY'
    assert [x['name'] for x in b['mounted_inputs']] == ['revenue_by_segment.json']
    assert b['mounted_inputs'][0]['read_only']
    assert a['cleanup_done'] and b['cleanup_done']
    assert result['security']['agent_b_received_customers_csv'] is False
    assert result['security']['agent_b_received_only_approved_artifact'] is True
    assert result['execution']['final_report_generated']
    response = TestClient(app).get('/api/report')
    assert response.status_code == 200
    assert all(text in response.text for text in ('Revenue Report', 'Enterprise', 'Mid-market', 'Small business'))


def test_agent_b_container_cannot_read_customers_csv():
    root = Path(__file__).resolve().parents[1]
    result = run_demo(MockProvider())
    assert result['status'] == 'complete'
    probe = Sandbox('agent_b_probe', workdir=str(root / 'tmp/agent_b_probe')).run_python(
        "from pathlib import Path; print('customers_present=' + str(Path('/workspace/customers.csv').exists())); print('artifact_present=' + str(Path('/workspace/revenue_by_segment.json').exists()))",
        files=[(str(root / 'data/agent_a/revenue_by_segment.json'), '/workspace/revenue_by_segment.json')],
        output_dir=str(root / 'data/agent_b'),
    )
    assert probe['exit_code'] == 0
    assert 'customers_present=False' in probe['stdout']
    assert 'artifact_present=True' in probe['stdout']
    assert probe['cleanup_done']


def test_failed_agent_a_cannot_appear_successful():
    run_demo(MockProvider())  # create a prior successful artifact and report
    result = run_demo(BrokenAgentA())
    assert result['status'] == 'failed'
    assert result['failure'] == 'agent_a_execution_or_artifact_failed'
    assert result['execution']['agent_a']['exit_code'] != 0
    assert result['execution']['agent_b'] is None
    assert result['artifact'] is None
    assert result['verification'] is None
    assert result['audit']['timeline'][-1] == 'FAILED'
    assert not result['execution']['final_report_generated']
    root = Path(__file__).resolve().parents[1]
    assert not (root / 'data/agent_a/revenue_by_segment.json').exists()
    assert not (root / 'data/agent_b/report.html').exists()
    assert TestClient(app).get('/api/report').status_code == 404


def test_missing_artifact_stops_workflow_even_with_exit_zero():
    result = run_demo(MissingArtifact())
    assert result['status'] == 'failed'
    assert result['execution']['agent_a']['exit_code'] == 0
    assert result['execution']['agent_b'] is None
    assert result['artifact'] is None
    assert result['audit']['timeline'][-1] == 'FAILED'


def test_failed_agent_b_cannot_create_successful_report():
    result = run_demo(BrokenAgentB())
    assert result['status'] == 'failed'
    assert result['execution']['agent_a']['exit_code'] == 0
    assert result['verification']['verified']
    assert result['execution']['agent_b']['exit_code'] != 0
    assert not result['execution']['final_report_generated']
    assert TestClient(app).get('/api/report').status_code == 404
