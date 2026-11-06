const timelineEl = document.getElementById('timeline');
const agentAEl = document.getElementById('agent-a-panel');
const gatewayEl = document.getElementById('gateway-panel');
const agentBEl = document.getElementById('agent-b-panel');
const runButton = document.getElementById('run-demo');

function renderJson(label, data) {
  return `
    <div class="card">
      <h3>${label}</h3>
      <pre>${JSON.stringify(data, null, 2)}</pre>
    </div>
  `;
}

function renderTimeline(items) {
  timelineEl.innerHTML = items
    .map((item) => `<span class="step">${item}</span>`)
    .join('');
}

async function runDemo() {
  runButton.disabled = true;
  runButton.textContent = 'Running...';

  try {
    const response = await fetch('/api/demo');
    const data = await response.json();

    renderTimeline(data.audit.timeline);

    agentAEl.innerHTML = `
      <div class="artifact-box">
        <strong>Private dataset</strong>
        <pre>${JSON.stringify({ filename: 'customers.csv', rows: 9 }, null, 2)}</pre>
      </div>
      ${renderJson('Approved request', data.request.replanned)}
      ${renderJson('Sandbox execution', data.execution.agent_a)}
      ${renderJson('Generated artifact', data.artifact)}
    `;

    gatewayEl.innerHTML = `
      ${renderJson('Original request', data.request.original)}
      ${renderJson('Denial', data.denial)}
      ${renderJson('Structured feedback', data.denial)}
      ${renderJson('Replanned request', data.request.replanned)}
      ${renderJson('Approved agreement', data.agreement)}
      ${renderJson('Verification', data.verification)}
      ${renderJson('Artifact release', data.security)}
    `;

    agentBEl.innerHTML = `
      ${renderJson('Original request', data.request.original)}
      ${renderJson('Replan', data.request.replanned)}
      ${renderJson('Received artifact', data.artifact)}
      ${renderJson('Report execution', data.execution.agent_b)}
      ${renderJson('Completed report', { status: data.status, final_report_generated: data.execution.final_report_generated })}
    `;
  } finally {
    runButton.disabled = false;
    runButton.textContent = 'Run Demo';
  }
}

runButton.addEventListener('click', runDemo);
runDemo();
