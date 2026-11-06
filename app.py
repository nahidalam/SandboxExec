import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from agreements import create_agreement, validate_agreement
from audit import AuditLog
from inference import InferenceError, get_provider
from policies import evaluate_policy
from sandbox import Sandbox
from verifier import verify_artifact

ROOT = Path(__file__).resolve().parent
RUN_LOCK = threading.Lock()
app = FastAPI(title='SandboxExec', version='0.1.0')
app.mount('/static', StaticFiles(directory=str(ROOT / 'static')), name='static')


@app.get('/')
def index():
    return FileResponse(str(ROOT / 'templates' / 'index.html'))


@app.get('/api/report')
def report():
    report_path = ROOT / 'data' / 'agent_b' / 'report.html'
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail='report not generated')
    return FileResponse(str(report_path))


@app.get('/api/demo')
def demo():
    return run_demo()


def run_demo(provider=None):
    with RUN_LOCK:
        return _run_demo(provider)


def _run_demo(provider):
    audit = AuditLog()
    agent_a_dir = ROOT / 'data' / 'agent_a'
    agent_b_dir = ROOT / 'data' / 'agent_b'
    agent_a_dir.mkdir(parents=True, exist_ok=True)
    agent_b_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = agent_a_dir / 'revenue_by_segment.json'
    report_path = agent_b_dir / 'report.html'
    artifact_path.unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)
    result = {
        'status': 'failed', 'failure': None,
        'inference': {'provider': None, 'model': None, 'completed_steps': []},
        'request': {'original': None, 'replanned': None},
        'denial': None, 'replan_policy': None, 'scoped_response': None,
        'agreement': None, 'agreement_validation': None,
        'artifact': None, 'verification': None,
        'execution': {'agent_a': None, 'agent_b': None, 'final_report_generated': False},
        'security': {'agent_b_received_customers_csv': False, 'artifact_release': None,
                     'agent_b_received_only_approved_artifact': False},
    }

    def finish():
        result['audit'] = audit.json()
        return result

    def fail(reason):
        result['failure'] = reason
        audit.log('FAILED', {'reason': reason})
        return finish()

    try:
        provider = provider or get_provider()
        result['inference']['provider'] = provider.provider_name
        result['inference']['model'] = getattr(provider, 'model', None)
        original_request = provider.get_initial_request()
        result['inference']['completed_steps'].append('initial_request')
        result['request']['original'] = original_request
        audit.log('REQUEST', {'requester': 'agent_b', 'text': original_request})
        denial = evaluate_policy(original_request)
        result['denial'] = denial
        audit.log('DENIED', denial)
        if denial['status'] != 'denied':
            return fail('initial_request_was_not_denied')

        replanned_request = provider.get_replanned_request(denial)
        result['inference']['completed_steps'].append('replanned_request')
        result['request']['replanned'] = replanned_request
        replan_policy = evaluate_policy(replanned_request)
        result['replan_policy'] = replan_policy
        audit.log('REPLAN', {'requester': 'agent_b', 'text': replanned_request, 'policy': replan_policy})
        if replan_policy['status'] != 'approved' or not all(
            word in replanned_request.lower() for word in ('revenue', 'segment')
        ):
            return fail('replanned_request_not_allowed')

        scoped_response = provider.get_scoped_response(replanned_request)
        result['inference']['completed_steps'].append('scoped_response')
        result['scoped_response'] = scoped_response
        agreement = create_agreement(
            requester='agent_b', provider='agent_a', resource='revenue_by_segment.json',
            operation='read', purpose='revenue_report', scope='current_task', status='approved',
        )
        agreement_validation = validate_agreement(agreement)
        result['agreement'] = agreement
        result['agreement_validation'] = agreement_validation
        audit.log('AGREEMENT', {'agreement': agreement, 'validation': agreement_validation,
                                'agent_a_response': scoped_response})
        if not agreement_validation['valid']:
            return fail('agreement_invalid')

        agent_a = Sandbox('agent_a', workdir=str(ROOT / 'tmp' / 'agent_a'))
        agent_a_result = agent_a.run_python(
            provider.get_agent_a_code(),
            files=[(str(ROOT / 'data' / 'customers.csv'), '/workspace/customers.csv')],
            output_dir=str(agent_a_dir),
        )
        result['execution']['agent_a'] = agent_a_result
        audit.log('EXECUTE', {'agent': 'agent_a', 'result': agent_a_result})
        if agent_a_result['exit_code'] != 0 or not artifact_path.is_file():
            return fail('agent_a_execution_or_artifact_failed')

        try:
            artifact = json.loads(artifact_path.read_text())
        except (OSError, json.JSONDecodeError):
            return fail('artifact_invalid_json')
        result['artifact'] = artifact
        verification = verify_artifact(artifact, agreement)
        result['verification'] = verification
        audit.log('VERIFY', verification)
        if not verification['verified']:
            return fail('artifact_verification_failed')

        agent_b = Sandbox('agent_b', workdir=str(ROOT / 'tmp' / 'agent_b'))
        agent_b_result = agent_b.run_python(
            provider.get_report_code(),
            files=[(str(artifact_path), '/workspace/revenue_by_segment.json')],
            output_dir=str(agent_b_dir),
        )
        result['execution']['agent_b'] = agent_b_result
        result['security']['agent_b_received_customers_csv'] = agent_b_result['customers_csv'] != 'NOT MOUNTED'
        result['security']['artifact_release'] = 'revenue_by_segment.json'
        result['security']['agent_b_received_only_approved_artifact'] = (
            len(agent_b_result['mounted_inputs']) == 1
            and agent_b_result['mounted_inputs'][0]['name'] == 'revenue_by_segment.json'
            and agent_b_result['mounted_inputs'][0]['read_only']
        )
        if agent_b_result['exit_code'] != 0 or not report_path.is_file():
            return fail('agent_b_execution_or_report_failed')
        if not result['security']['agent_b_received_only_approved_artifact']:
            report_path.unlink(missing_ok=True)
            return fail('agent_b_input_isolation_failed')
        result['execution']['final_report_generated'] = True
        result['status'] = 'complete'
        audit.log('COMPLETE', {'status': 'complete', 'final_report_path': str(report_path),
                               'agent_b_result': agent_b_result})
        return finish()
    except InferenceError as exc:
        return fail(str(exc))
    except Exception as exc:
        # Never include unexpected exception text: it may contain sensitive data.
        return fail('workflow_error_' + type(exc).__name__)


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=False)
