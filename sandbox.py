import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path


IMAGE = 'python:3.12-slim'


class Sandbox:
    def __init__(self, name: str, workdir: str | None = None):
        self.name = name
        self.workdir = Path(workdir) if workdir else Path('/tmp') / f'sandboxexec-{name}-{uuid.uuid4().hex}'
        self.workdir.mkdir(parents=True, exist_ok=True)

    def run_python(self, code: str, files: list | None = None, output_dir: str | None = None, timeout: int = 120):
        started = time.monotonic()
        container_name = f'sandboxexec-{self.name}-{uuid.uuid4().hex[:12]}'
        output_root = Path(output_dir) if output_dir else self.workdir / 'output'
        output_root.mkdir(parents=True, exist_ok=True)
        os.chown(output_root, 1000, 1000)
        output_root.chmod(0o700)
        script_path = self.workdir / 'script.py'
        script_path.write_text(code)
        script_path.chmod(0o644)
        mounted_inputs = []
        mounts = ['-v', f'{self.workdir.resolve()}:/workspace:ro']
        error = None
        for host_path, container_path in files or []:
            host = Path(host_path).resolve()
            if not host.is_file():
                error = f'Input file missing: {host.name}'
                break
            if not container_path.startswith('/workspace/') or '/' in container_path[len('/workspace/'):]:
                error = 'Input mount must be a direct child of /workspace'
                break
            (self.workdir / Path(container_path).name).touch()
            mounts.extend(['-v', f'{host}:{container_path}:ro'])
            mounted_inputs.append({'name': host.name, 'container_path': container_path, 'read_only': True})
        mounts.extend(['-v', f'{output_root.resolve()}:/output:rw'])
        command = [
            'docker', 'run', '--rm', '--name', container_name,
            '--network', 'none', '--cap-drop=ALL',
            '--security-opt', 'no-new-privileges', '--read-only',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
            '--pids-limit', '64', '--cpus', '0.5', '--memory', '256m',
            '--user', '1000:1000', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '-w', '/workspace', *mounts,
            IMAGE, 'python', '/workspace/script.py',
        ]
        exit_code, stdout, stderr = None, '', ''
        try:
            if error:
                exit_code, stderr = 1, error
            else:
                completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
                exit_code, stdout, stderr = completed.returncode, completed.stdout.strip(), completed.stderr.strip()
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = (exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
            stderr = f'Execution timed out after {timeout} seconds'
            subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True, timeout=15)
        except OSError as exc:
            exit_code, stderr = 1, f'Docker invocation failed: {exc.strerror or type(exc).__name__}'
        finally:
            shutil.rmtree(self.workdir, ignore_errors=True)
        try:
            inspect = subprocess.run(['docker', 'container', 'inspect', container_name], capture_output=True, timeout=10)
            container_removed = inspect.returncode != 0
        except (OSError, subprocess.TimeoutExpired):
            container_removed = False
        cleanup_done = not self.workdir.exists() and container_removed
        return {
            'agent': self.name,
            'sandbox_id': container_name,
            'docker_image': IMAGE,
            'exit_code': exit_code,
            'stdout': stdout,
            'stderr': stderr,
            'duration_seconds': round(time.monotonic() - started, 3),
            'mounted_inputs': mounted_inputs,
            'customers_csv': 'MOUNTED READ-ONLY' if any(item['name'] == 'customers.csv' for item in mounted_inputs) else 'NOT MOUNTED',
            'revenue_by_segment_json': 'MOUNTED READ-ONLY' if any(item['name'] == 'revenue_by_segment.json' for item in mounted_inputs) else 'NOT MOUNTED',
            'network_disabled': True,
            'cpu_limit': '0.5 CPU',
            'memory_limit': '256m',
            'pid_limit': 64,
            'cleanup_done': cleanup_done,
        }
