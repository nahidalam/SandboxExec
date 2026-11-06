# SandboxExec

SandboxExec demonstrates a private-data agent workflow: **REQUEST → DENIED → REPLAN → AGREEMENT → EXECUTE → VERIFY → COMPLETE**. The policy, agreement, artifact verification, access control, and Docker isolation are deterministic. The browser reads the actual backend result; it does not animate or substitute a successful outcome.

## Demo

- Agent B asks for customer-level records. Policy denies the request and returns structured feedback.
- Agent B replans to request revenue aggregated by segment. The replan is evaluated again.
- A scoped agreement authorizes only `revenue_by_segment.json` for this report.
- Agent A executes Python in Docker with `customers.csv` mounted read-only and writes the aggregate JSON artifact.
- The verifier reads the generated JSON, validates its schema, and checks the agreement.
- Agent B executes separately in Docker with only the approved JSON mounted read-only. It writes `report.html`.
- Any failed execution, missing artifact, invalid artifact, or missing report stops the workflow and is reported as failed.

Both containers have no network, a read-only root filesystem, dropped capabilities, no new privileges, 0.5 CPU, 256 MB memory, and a 64 PID limit. Docker runs with `--rm`; the response records actual exit codes, stdout, stderr, elapsed time, mounts, and cleanup checks.

## VM setup

On an Ubuntu 24.04 VM with Docker and Python 3.12:

```bash
cd /root/SandboxExec
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
LLM_PROVIDER=mock .venv/bin/python -m pytest -q
```

Create `/etc/sandboxexec/sandboxexec.env` owned by root with mode `0600`:

```text
LLM_PROVIDER=mock
```

For Vultr inference, set `LLM_PROVIDER=vultr` and add `VULTR_INFERENCE_BASE_URL`, `VULTR_INFERENCE_API_KEY`, and `VULTR_MODEL` to that file. The base URL is the HTTPS API root ending in `/v1`, such as `https://api.vultrinference.com/v1`. Use a model available to your Serverless Inference subscription. The provider calls `POST /chat/completions` for the original request, a replan containing structured policy feedback, and Agent A's scoped response. It never falls back to mock inference if the API fails. Docker code templates remain fixed to make the data and report behavior reproducible.

Install and start the included systemd service and nginx site:

```bash
cp deploy/sandboxexec.service /etc/systemd/system/sandboxexec.service
systemctl daemon-reload
systemctl enable --now sandboxexec
cp deploy/nginx.conf /etc/nginx/sites-available/sandboxexec
ln -s /etc/nginx/sites-available/sandboxexec /etc/nginx/sites-enabled/sandboxexec
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Open the VM's public IP in a browser. `GET /api/demo` executes the full workflow and `GET /api/report` returns the report only after a successful run. The protected systemd environment file is outside the repository. `.env`, generated reports, temporary files, logs, and virtual environments are ignored by Git.
