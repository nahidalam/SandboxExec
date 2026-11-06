const timelineEl = document.getElementById('timeline');
const agentAEl = document.getElementById('agent-a-panel');
const gatewayEl = document.getElementById('gateway-panel');
const agentBEl = document.getElementById('agent-b-panel');
const runButton = document.getElementById('run-demo');

const workflowSteps = ['REQUEST', 'DENIED', 'REPLAN', 'AGREEMENT', 'EXECUTE', 'VERIFY', 'COMPLETE'];

function evidenceBlock(label, payload) {
  return `
    <div class="evidence" hidden>
      <div class="card-label">${label}</div>
      <pre>${JSON.stringify(payload, null, 2)}</pre>
    </div>
  `;
}

function renderTimeline(activeIndex = -1) {
  timelineEl.innerHTML = workflowSteps
    .map((step, index) => {
      const classes = ['step'];
      if (index <= activeIndex) classes.push('active');
      if (index <= activeIndex && step !== 'DENIED') classes.push('success');
      if (step === 'DENIED' && index <= activeIndex) classes.push('security');
      return `<span class="${classes.join(' ')}" data-step="${step}">${step}</span>`;
    })
    .join('');
}

function animateTimeline() {
  renderTimeline(-1);
  workflowSteps.forEach((step, index) => {
    setTimeout(() => {
      renderTimeline(index);
    }, 350 * (index + 1));
  });
}

function renderEvidenceButton(id, label = 'View evidence') {
  return `<button class="ghost evidence-toggle" data-target="${id}">${label}</button>`;
}

function toggleEvidence(event) {
  const button = event.target.closest('.evidence-toggle');
  if (!button) return;
  const target = button.parentElement.querySelector('.evidence');
  if (!target) return;
  const isHidden = target.hasAttribute('hidden');
  target.toggleAttribute('hidden', !isHidden);
  button.textContent = isHidden ? 'Hide evidence' : 'View evidence';
}

function renderAgreementCard(data) {
  const agreement = data.agreement;
  return `
    <div class="card">
      <div class="card-head">
        <div class="card-label">Agreement</div>
        <span class="status approved">Approved</span>
      </div>
      <div class="big">AGREEMENT APPROVED</div>
      <ul class="list">
        <li>Resource: ${agreement.resource.replace('_', ' ')}</li>
        <li>Access: ${agreement.operation}</li>
        <li>Purpose: ${agreement.purpose.replace('_', ' ')}</li>
        <li>Scope: ${agreement.scope.replace('_', ' ')}</li>
      </ul>
      ${renderEvidenceButton('gateway-agreement')}
      ${evidenceBlock('Agreement JSON', agreement)}
    </div>
  `;
}

function renderGateway(data) {
  const denial = data.denial;
  const verification = data.verification;

  gatewayEl.innerHTML = `
    <div class="card">
      <div class="card-head">
        <div class="card-label">Original Request</div>
      </div>
      <div class="big">Agent B requests customer-level revenue records</div>
      ${evidenceBlock('Original request', data.request.original)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Security decision</div>
      </div>
      <div class="status denied">Denied</div>
      <div class="big">Customer-level records are restricted.</div>
      ${evidenceBlock('Structured denial', denial)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Structured Feedback</div>
      </div>
      <div class="big">Available alternative</div>
      <div class="quote">Revenue aggregated by customer segment</div>
      ${evidenceBlock('Structured feedback', denial)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Replan</div>
      </div>
      <div class="big">Agent B adapts its request</div>
      <div class="quote">“Provide revenue aggregated by customer segment for this report.”</div>
      ${evidenceBlock('Replanned request', data.request.replanned)}
    </div>

    ${renderAgreementCard(data)}

    <div class="card">
      <div class="card-head">
        <div class="card-label">Verification</div>
      </div>
      <div class="status verified">Verified</div>
      <div class="big">ARTIFACT VERIFIED</div>
      <ul class="list">
        <li>Valid format ✓</li>
        <li>Aggregate data only ✓</li>
        <li>No customer identifiers ✓</li>
        <li>Agreement satisfied ✓</li>
      </ul>
      ${renderEvidenceButton('gateway-verification')}
      ${evidenceBlock('Verification result', verification)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Artifact Release</div>
      </div>
      <div class="big">Verified artifact released to Agent B</div>
      <div class="muted">customers.csv remained inside Agent A's sandbox</div>
      ${renderEvidenceButton('gateway-release')}
      ${evidenceBlock('Release metadata', data.security)}
    </div>
  `;

  gatewayEl.querySelectorAll('.evidence-toggle').forEach((button) => {
    button.addEventListener('click', toggleEvidence);
  });
}

function renderAgentA(data) {
  const artifact = data.artifact;
  agentAEl.innerHTML = `
    <div class="card">
      <div class="card-head">
        <div class="card-label">Private Dataset</div>
      </div>
      <div class="big">9 customer records</div>
      <div class="muted">customers.csv · private to Agent A</div>
      ${evidenceBlock('Private dataset metadata', { filename: 'customers.csv', rows: 9 })}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Approved Request</div>
      </div>
      <div class="big">Generate revenue by customer segment</div>
      ${evidenceBlock('Approved request', data.request.replanned)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Sandbox Execution</div>
      </div>
      <div class="big">Analysis completed successfully</div>
      <div class="badges">
        <span class="badge">Docker</span>
        <span class="badge">Exit 0</span>
        <span class="badge">1.2s</span>
      </div>
      ${renderEvidenceButton('agent-a-execution')}
      ${evidenceBlock('Agent A execution', data.execution.agent_a)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Generated Artifact</div>
      </div>
      <div class="big">Revenue by segment</div>
      <ul class="list">
        <li>Enterprise: $620,000</li>
        <li>Mid-market: $410,000</li>
        <li>Small business: $170,000</li>
      </ul>
      ${renderEvidenceButton('agent-a-artifact')}
      ${evidenceBlock('Artifact payload', artifact)}
    </div>

    <script>
      // no-op placeholder to keep browser parse clean
    </script>
  `;

  agentAEl.querySelectorAll('.evidence-toggle').forEach((button) => {
    button.addEventListener('click', toggleEvidence);
  });
}

function renderAgentB(data) {
  agentBEl.innerHTML = `
    <div class="card">
      <div class="card-head">
        <div class="card-label">Original Request</div>
      </div>
      <div class="big">Customer-level records and revenue data</div>
      ${evidenceBlock('Original request', data.request.original)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Replan</div>
      </div>
      <div class="big">Revenue aggregated by customer segment</div>
      <div class="muted">Adapted from policy feedback</div>
      ${evidenceBlock('Replanned request', data.request.replanned)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Received Artifact</div>
      </div>
      <ul class="list">
        <li>Enterprise: $620,000</li>
        <li>Mid-market: $410,000</li>
        <li>Small business: $170,000</li>
      </ul>
      ${evidenceBlock('Received artifact', data.artifact)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Report Execution</div>
      </div>
      <div class="big">Report generated successfully</div>
      <div class="badges">
        <span class="badge">Docker</span>
        <span class="badge">Exit 0</span>
        <span class="badge">1.2s</span>
      </div>
      ${renderEvidenceButton('agent-b-execution')}
      ${evidenceBlock('Agent B execution', data.execution.agent_b)}
    </div>

    <div class="card">
      <div class="card-head">
        <div class="card-label">Completed Report</div>
      </div>
      <div class="big">Revenue report completed</div>
      <button class="secondary" id="view-report">View Report</button>
      ${evidenceBlock('Final report status', { status: data.status, final_report_generated: data.execution.final_report_generated })}
    </div>
  `;

  agentBEl.querySelectorAll('.evidence-toggle').forEach((button) => {
    button.addEventListener('click', toggleEvidence);
  });

  const reportButton = document.getElementById('view-report');
  if (reportButton) {
    reportButton.addEventListener('click', () => {
      window.open('/api/report', '_blank');
    });
  }
}

async function runDemo() {
  runButton.disabled = true;
  runButton.textContent = 'Running...';
  animateTimeline();

  try {
    const response = await fetch('/api/demo');
    const data = await response.json();

    renderAgentA(data);
    renderGateway(data);
    renderAgentB(data);
    renderTimeline(workflowSteps.length - 1);
  } finally {
    runButton.disabled = false;
    runButton.textContent = 'Run Demo';
  }
}

runButton.addEventListener('click', runDemo);
renderTimeline(-1);
runDemo();
