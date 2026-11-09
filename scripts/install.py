"""Initialize a cloned ziikoo-imagegen skill without storing API credentials."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home() / '.ziikoo-imagegen'


def run(*args, cwd=ROOT, quiet=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.DEVNULL if quiet else None,
                          stderr=subprocess.STDOUT if quiet else None)


def normalize(url):
    return url.strip().removesuffix('.git').rstrip('/')


def initialize(skip_deps=False):
    if sys.version_info < (3, 11):
        raise ValueError('python_3_11_or_newer_required')
    release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    top_path = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT,
                                       text=True, stderr=subprocess.DEVNULL).strip()
    if Path(top_path).resolve() != ROOT:
        raise ValueError('standalone_git_checkout_required')
    remote = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], cwd=ROOT,
                                     text=True, stderr=subprocess.DEVNULL).strip()
    if normalize(remote) != normalize(release['repository']):
        raise ValueError('trusted_release_repository_mismatch')
    if not skip_deps:
        run(sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt')
    run(sys.executable, '-B', 'scripts/offline_test.py', quiet=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    version = json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))['version']
    STATE.mkdir(parents=True, exist_ok=True)
    state = {
        'version': version,
        'commit': commit,
        'repository': release['repository'],
        'installed_at': time.time(),
        'python': sys.version.split()[0]
    }
    (STATE / 'install.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-deps', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(initialize(args.skip_deps), ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__,
                          'message': str(exc)[:500]}, ensure_ascii=False))
        raise SystemExit(1)
