"""Optional dependency vulnerability scans; never installs fixes."""
import json
from pathlib import Path
import shutil
import subprocess
import sys


def dependency_scan(directory, ecosystems, output):
    root = Path(directory).resolve(); out = Path(output).resolve(); out.mkdir(parents=True, exist_ok=True)
    results = []
    for ecosystem in ecosystems:
        try:
            if ecosystem == 'npm':
                if not (root / 'package-lock.json').exists(): raise ValueError('npm scan requires package-lock.json')
                executable = shutil.which('npm')
                if not executable: raise ValueError('npm not installed')
                command = [executable, 'audit', '--json', '--ignore-scripts']
            elif ecosystem == 'python':
                lock = root / 'requirements.txt'
                if not lock.exists(): raise ValueError('Python scan requires requirements.txt')
                # Require a fully pinned exported dependency list; no builds or dependency resolution.
                lines = [line.strip() for line in lock.read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
                import re
                if not lines or any(not re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+', line) for line in lines):
                    raise ValueError('Supply a separate folder with fully pinned, transitive name==version requirements for --no-deps audit')
                command = [sys.executable, '-m', 'pip_audit', '-r', str(lock), '--no-deps', '--disable-pip', '--format', 'json']
            else: raise ValueError('Unknown ecosystem')
            proc = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=180)
            data = json.loads(proc.stdout)
            (out / (ecosystem + '-audit.json')).write_text(json.dumps(data, indent=2))
            if ecosystem == 'npm':
                if 'error' in data or 'metadata' not in data: raise ValueError('npm did not produce vulnerability summary')
                count = data['metadata']['vulnerabilities']['total']
            else:
                dependencies = data.get('dependencies', []) if isinstance(data, dict) else data
                if any(d.get('skip_reason') for d in dependencies): raise ValueError('One or more dependencies were not scanned')
                if not isinstance(dependencies, list) or not dependencies or any('vulns' not in d for d in dependencies): raise ValueError('Missing dependency audit data')
                count = sum(len(d.get('vulns', [])) for d in dependencies)
            if not isinstance(count, int) or count < 0 or (proc.returncode == 1 and count == 0): raise ValueError('Inconsistent scanner result')
            if proc.returncode not in (0, 1): raise ValueError('Scanner execution failed')
            results.append({'name': ecosystem, 'status': 'FAIL' if count else 'PASS', 'known_vulnerability_count': count})
        except Exception as exc:
            results.append({'name': ecosystem, 'status': 'ERROR', 'detail': str(exc)[:300]})
    return {'kind': 'dependency-security', 'results': results, 'passed': bool(results) and all(r['status'] == 'PASS' for r in results), 'limitation': 'Known dependency advisories only. Uses external advisory services. Not a penetration test or proof of exploitability.'}
