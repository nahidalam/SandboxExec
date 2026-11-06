const timelineEl = document.getElementById('timeline');
const agentAEl = document.getElementById('agent-a-panel');
const gatewayEl = document.getElementById('gateway-panel');
const agentBEl = document.getElementById('agent-b-panel');
const runButton = document.getElementById('run-demo');
const steps = ['REQUEST', 'DENIED', 'REPLAN', 'AGREEMENT', 'EXECUTE', 'VERIFY', 'COMPLETE'];

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
}

function evidence(label, payload) {
  return `<button class="ghost evidence-toggle">View evidence</button>
    <div class="evidence" hidden><div class="card-label">${esc(label)}</div><pre>${esc(JSON.stringify(payload, null, 2))}</pre></div>`;
}

function card(label, body, detailLabel, detail) {
  return `<div class="card"><div class="card-head"><div class="card-label">${esc(label)}</div></div>${body}${detailLabel ? evidence(detailLabel, detail) : ''}</div>`;
}

function renderTimeline(timeline = []) {
  const visible = [...steps];
  if (timeline.includes('FAILED')) visible.push('FAILED');
  timelineEl.innerHTML = visible.map(step => {
    const active = timeline.includes(step);
    const classes = ['step'];
    if (active) classes.push('active', step === 'DENIED' || step === 'FAILED' ? 'security' : 'success');
    return `<span class="${classes.join(' ')}" data-step="${step}">${step}</span>`;
  }).join('');
}

function artifactRows(artifact) {
  if (!artifact) return '';
  const labels = {enterprise: 'Enterprise', mid_market: 'Mid-market', small_business: 'Small business'};
  return `<ul class="list">${Object.entries(artifact).map(([key, value]) =>
    `<li>${esc(labels[key] || key)}: $${Number(value).toLocaleString()}</li>`).join('')}</ul>`;
}

function executionCard(label, result) {
  if (!result) return '';
  const passed = result.exit_code === 0;
  return card(label,
    `<div class="big">${passed ? 'Execution succeeded' : 'Execution failed'}</div>
     <div class="badges"><span class="badge">${esc(result.docker_image)}</span>
     <span class="badge">Exit ${esc(result.exit_code)}</span>
     <span class="badge">${esc(result.duration_seconds)}s</span></div>`,
    `${label} evidence`, result);
}

function renderAgentA(data) {
  let html = card('Private Dataset', '<div class="big">customers.csv</div><div class="muted">Private to Agent A</div>');
  if (data.request.replanned) html += card('Approved Request', `<div class="big">${esc(data.request.replanned)}</div>`);
  html += executionCard('Sandbox Execution', data.execution.agent_a);
  if (data.artifact) html += card('Generated Artifact', `<div class="big">Revenue by segment</div>${artifactRows(data.artifact)}`, 'Artifact payload', data.artifact);
  agentAEl.innerHTML = html;
}

function renderGateway(data) {
  let html = '';
  if (data.request.original) html += card('Original Request', `<div class="big">${esc(data.request.original)}</div>`, 'Original request', data.request.original);
  if (data.denial) html += card('Security decision', `<div class="status ${data.denial.status === 'denied' ? 'denied' : ''}">${esc(data.denial.status)}</div><div class="big">${esc(data.denial.reason)}</div>`, 'Structured feedback', data.denial);
  if (data.request.replanned) html += card('Replan', `<div class="big">${esc(data.request.replanned)}</div>`, 'Replan policy', data.replan_policy);
  if (data.agreement) html += card('Agreement', `<div class="status ${data.agreement_validation?.valid ? 'approved' : 'denied'}">${data.agreement_validation?.valid ? 'Approved' : 'Invalid'}</div><ul class="list"><li>Resource: ${esc(data.agreement.resource)}</li><li>Access: ${esc(data.agreement.operation)}</li><li>Purpose: ${esc(data.agreement.purpose)}</li><li>Scope: ${esc(data.agreement.scope)}</li></ul>`, 'Agreement and scoped response', {agreement: data.agreement, validation: data.agreement_validation, agent_a_response: data.scoped_response});
  if (data.verification) html += card('Verification', `<div class="status ${data.verification.verified ? 'verified' : 'denied'}">${data.verification.verified ? 'Verified' : 'Failed'}</div><div class="big">${data.verification.verified ? 'ARTIFACT VERIFIED' : 'ARTIFACT REJECTED'}</div>`, 'Verification result', data.verification);
  if (data.security.artifact_release) html += card('Artifact Release', `<div class="big">${data.security.agent_b_received_only_approved_artifact ? 'Verified artifact released to Agent B' : 'Artifact access failed'}</div><div class="muted">customers.csv — ${esc(data.execution.agent_b?.customers_csv || 'unknown')}<br>revenue_by_segment.json — ${esc(data.execution.agent_b?.revenue_by_segment_json || 'unknown')}</div>`, 'Release and mount evidence', {security: data.security, mounted_inputs: data.execution.agent_b?.mounted_inputs});
  if (data.failure) html += card('Workflow Failed', `<div class="status denied">Failed</div><div class="big">${esc(data.failure)}</div>`, 'Audit trail', data.audit);
  gatewayEl.innerHTML = html;
}

function renderAgentB(data) {
  let html = '';
  if (data.request.original) html += card('Original Request', `<div class="big">${esc(data.request.original)}</div>`);
  if (data.request.replanned) html += card('Replan', `<div class="big">${esc(data.request.replanned)}</div>`);
  if (data.execution.agent_b && data.artifact) html += card('Received Artifact', artifactRows(data.artifact), 'Received artifact', data.artifact);
  html += executionCard('Report Execution', data.execution.agent_b);
  if (data.status === 'complete' && data.execution.final_report_generated) {
    html += card('Completed Report', '<div class="big">Revenue report completed</div><button class="secondary" id="view-report">View Report</button>', 'Final report status', {status: data.status, final_report_generated: true});
  }
  agentBEl.innerHTML = html;
  document.getElementById('view-report')?.addEventListener('click', () => window.open('/api/report', '_blank'));
}

document.addEventListener('click', event => {
  const button = event.target.closest('.evidence-toggle');
  if (!button) return;
  const target = button.nextElementSibling;
  const show = target.hasAttribute('hidden');
  target.toggleAttribute('hidden', !show);
  button.textContent = show ? 'Hide evidence' : 'View evidence';
});

async function runDemo() {
  runButton.disabled = true;
  runButton.textContent = 'Running...';
  renderTimeline();
  try {
    const response = await fetch('/api/demo');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    renderAgentA(data);
    renderGateway(data);
    renderAgentB(data);
    renderTimeline(data.audit?.timeline || []);
  } catch (error) {
    gatewayEl.innerHTML = card('Workflow Failed', `<div class="status denied">Failed</div><div class="big">${esc(error.message)}</div>`);
    renderTimeline(['FAILED']);
  } finally {
    runButton.disabled = false;
    runButton.textContent = 'Run Demo';
  }
}

function renderIdle() {
  agentAEl.innerHTML = card('Status', '<div class="big">Ready</div><div class="muted">Private data owner</div>');
  gatewayEl.innerHTML = card('Status', '<div class="big">Ready</div><div class="muted">Waiting for agent request</div>');
  agentBEl.innerHTML = card('Status', '<div class="big">Ready</div><div class="muted">Report agent</div>');
}

runButton.addEventListener('click', runDemo);
renderTimeline();
renderIdle();
