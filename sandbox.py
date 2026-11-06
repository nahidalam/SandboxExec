import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path


class Sandbox:
    def __init__(self, name: str, workdir: str | None = None):
        self.name = name
        base = Path(workdir) if workdir else Path('/tmp') / f'sandboxexec-{name}-{uuid.uuid4().hex}'
        base.mkdir(parents=True, exist_ok=True)
        self.workdir = base

    def run_python(self, code: str, files: list | None = None, output_dir: str | None = None, timeout: int = 120):
        script_path = self.workdir / 'script.py'
        script_path.write_text(code)
        output_root = Path(output_dir) if output_dir else self.workdir / 'output'
        output_root.mkdir(parents=True, exist_ok=True)
        mounts = [
            '-v', f'{self.workdir}:/workspace:rw',
        ]
        for host_path, container_path in (files or []):
            host = Path(host_path)
            if host.exists():
                mounts.extend(['-v', f'{host}:{container_path}:ro'])

        mounts.extend(['-v', f'{output_root}:/output:rw'])

        cmd = [
            'docker', 'run', '--rm',
            '--network', 'none',
            '--cap-drop=ALL',
            '--security-opt', 'no-new-privileges',
            '--read-only',
            '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
            '--pids-limit', '64',
            '--cpus', '0.5',
            '--memory', '256m',
            '--user', '1000:1000',
            '-w', '/workspace',
            *mounts,
            'python:3.12-slim',
            'python', '/workspace/script.py',
        ]

        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(Path.cwd()),
        )

        for candidate in self.workdir.iterdir():
            if candidate.name == 'script.py':
                continue
            target = output_root / candidate.name
            if candidate.is_file():
                shutil.copy2(candidate, target)

        cleanup_done = False
        try:
            shutil.rmtree(self.workdir, ignore_errors=True)
            cleanup_done = True
        except Exception:
            cleanup_done = False

        return {
            'exit_code': completed.returncode,
            'stdout': completed.stdout.strip(),
            'stderr': completed.stderr.strip(),
            'duration_seconds': timeout,
            'files': str(output_root),
            'cleanup_done': cleanup_done,
        }
