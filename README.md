# SandboxExec

SandboxExec enables AI agents to negotiate task-specific permissions, establish enforceable agreements, and collaborate securely across isolated execution environments.

Built for the Vultr Agent Rush Hackathon — Challenge 1: Blast Radius Zero.

## What it does

SandboxExec is a minimal secure multi-agent execution platform that demonstrates the full loop of:

Deny → Replan → Negotiate → Execute → Verify → Complete

It models a private-data workflow where an agent with restricted access denies a dangerous request, a second agent replans to an approved aggregate alternative, a scoped agreement is created, real Python executes inside isolated Docker sandboxes, the artifact is check-verified, and the final report is released only after validation.

## Local MVP workflow

- Agent B requests customer-level records.
- The policy layer denies the request and returns structured feedback.
- Agent B replans to a safe aggregate-only request.
- The agreement gateway approves a scoped read for the report task.
- Agent A runs Python in Docker to compute revenue by segment.
- The verifier checks schema, aggregate-only fields, and agreement compliance.
- Agent B runs in its own Docker sandbox to create a final HTML report.
- The browser UI shows the timeline and technical evidence.

## Local setup

1. Create and activate a virtual environment:

   python -m venv .venv
   source .venv/bin/activate

2. Install dependencies:

   python -m pip install -r requirements.txt

3. Verify Docker is available:

   docker --version

4. Run the app with the mock provider:

   LLM_PROVIDER=mock python -m uvicorn app:app --host 0.0.0.0 --port 8000

5. Open the browser UI:

   http://localhost:8000

6. Run tests:

   pytest -q

## Vultr deployment (future-ready)

The project is prepared for Vultr integration without requiring credentials for the local demo.

- One Vultr Cloud Compute VM hosts the FastAPI app
- Docker sandboxes run on the same VM for isolated agent execution
- Vultr Serverless Inference can be enabled later via environment variables
- Configuration uses:

  LLM_PROVIDER=mock
  VULTR_INFERENCE_BASE_URL=
  VULTR_INFERENCE_API_KEY=
  VULTR_MODEL=

When the endpoint, key, and model are supplied, switching to `LLM_PROVIDER=vultr` activates the same workflow with the Vultr provider interface.

## Security model

- Separate Docker sandbox per agent
- Network disabled for execution
- Read-only root filesystem
- Limited CPU, memory, PID count, and timeouts
- Dropped Linux capabilities and no-new-privileges
- Only the approved artifact is transferred to Agent B
- Customer CSV never reaches Agent B

## Files

Core implementation is intentionally compact and readable, centered around:

- app.py
- policies.py
- agreements.py
- inference.py
- sandbox.py
- verifier.py
- audit.py
- templates/index.html
- static/app.js
- static/style.css
