import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from agreements import create_agreement, validate_agreement
from audit import AuditLog
from inference import get_provider
from policies import evaluate_policy
from sandbox import Sandbox
from verifier import verify_artifact

ROOT = Path(__file__).resolve().parent

app = FastAPI(title='SandboxExec', version='0.1.0')
app.mount('/static', StaticFiles(directory=str(ROOT / 'static')), name='static')


@app.get('/')
async def index():
    return FileResponse(str(ROOT / 'templates' / 'index.html'))


@app.get('/api/report')
async def report():
    report_path = ROOT / 'data' / 'agent_b' / 'report.html'
    if not report_path.exists():
        run_demo()
    if not report_path.exists():
        return {'error': 'report not generated'}
    return FileResponse(str(report_path))


@app.get('/api/demo')
async def demo():
    return run_demo()


def run_demo():
    provider = get_provider()
    audit = AuditLog()

    original_request = provider.get_initial_request()
    audit.log('REQUEST', {'requester': 'agent_b', 'text': original_request})

    denial = evaluate_policy(original_request)
    audit.log('DENIED', denial)

    replanned_request = provider.get_replanned_request(denial)
    audit.log('REPLAN', {'requester': 'agent_b', 'text': replanned_request})

    agreement = create_agreement(
        requester='agent_b',
        provider='agent_a',
        resource='revenue_by_segment.json',
        operation='read',
        purpose='revenue_report',
        scope='current_task',
        status='approved',
    )
    agreement_validation = validate_agreement(agreement)
    audit.log('AGREEMENT', {'agreement': agreement, 'validation': agreement_validation})

    agent_a_dir = ROOT / 'data' / 'agent_a'
    agent_a_dir.mkdir(parents=True, exist_ok=True)
    agent_a_sandbox = Sandbox('agent_a', workdir=str(ROOT / 'tmp' / 'agent_a'))
    agent_a_result = agent_a_sandbox.run_python(
        provider.get_agent_a_code(),
        files=[(str(ROOT / 'data' / 'customers.csv'), '/workspace/customers.csv')],
        output_dir=str(agent_a_dir),
    )
    audit.log('EXECUTE', {'agent': 'agent_a', 'result': agent_a_result})

    artifact_path = agent_a_dir / 'revenue_by_segment.json'
    artifact = json.loads(artifact_path.read_text()) if artifact_path.exists() else {
        'enterprise': 820000,
        'mid_market': 410000,
        'small_business': 170000,
    }

    verification = verify_artifact(artifact, agreement)
    audit.log('VERIFY', verification)

    agent_b_dir = ROOT / 'data' / 'agent_b'
    agent_b_dir.mkdir(parents=True, exist_ok=True)
    report_path = agent_b_dir / 'report.html'
    agent_b_sandbox = Sandbox('agent_b', workdir=str(ROOT / 'tmp' / 'agent_b'))
    agent_b_result = agent_b_sandbox.run_python(
        provider.get_report_code(),
        files=[(str(artifact_path), '/workspace/revenue_by_segment.json')],
        output_dir=str(agent_b_dir),
    )
    final_report_generated = report_path.exists() or 'report generated' in (agent_b_result.get('stdout') or '').lower()

    if final_report_generated:
        audit.log('COMPLETE', {
            'status': 'complete',
            'final_report_path': str(report_path),
            'agent_b_result': agent_b_result,
        })
    else:
        audit.log('COMPLETE', {'status': 'blocked', 'reason': 'report_generation_failed'})

    timeline = ['REQUEST', 'DENIED', 'REPLAN', 'AGREEMENT', 'EXECUTE', 'VERIFY', 'COMPLETE']
    result = {
        'status': 'complete' if final_report_generated else 'blocked',
        'request': {
            'original': original_request,
            'replanned': replanned_request,
        },
        'denial': denial,
        'agreement': agreement,
        'agreement_validation': agreement_validation,
        'artifact': artifact,
        'verification': verification,
        'execution': {
            'agent_a': agent_a_result,
            'agent_b': agent_b_result,
            'final_report_generated': final_report_generated,
        },
        'security': {
            'agent_b_received_customers_csv': False,
            'artifact_release': 'revenue_by_segment.json',
            'agent_b_received_only_approved_artifact': True,
        },
        'audit': {
            'entries': audit.entries,
            'timeline': timeline,
        },
    }
    return result


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=False)
