"""Daily fast-forward update from the trusted repository recorded in release.json."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import hashlib
from runtime import ROOT, BUNDLED
if not BUNDLED:
    ROOT = Path(__file__).resolve().parents[1]

STATE = Path.home() / '.imagegen-dual'


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True, encoding="utf-8", timeout=45).strip()


def normalize(url):
    return url.strip().removesuffix('.git').rstrip('/')


def smoke(root):
    # This check belongs to the installed updater, not the candidate's tests.
    code = "import client, accounts; from PIL import Image; assert callable(client.generate); assert callable(accounts.discover)"
    subprocess.run([sys.executable, '-B', '-c', code], cwd=root / 'scripts', check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


def update(auto=False):
    if BUNDLED:
        return {'status': 'portable_manual_update', 'message': 'Install a verified replacement package alongside the current one.'}
    cfg = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    STATE.mkdir(parents=True, exist_ok=True)
    marker = STATE / ('last-update-check-' + hashlib.sha256(str(ROOT).encode()).hexdigest()[:12])
    if auto and marker.exists() and time.time() - marker.stat().st_mtime < 86400:
        return {'status': 'checked_recently'}
    remote = cfg['repository']
    branch = cfg.get('branch', 'main')
    if not remote.startswith('https://') or '@' in remote or '?' in remote or '#' in remote:
        raise ValueError('public_https_repository_required')
    if not branch or branch.startswith('-') or not all(c.isalnum() or c in '/-._' for c in branch):
        raise ValueError('invalid_branch')
    # Reject a parent repository: an installation must be its own checkout.
    try:
        top = Path(git('rev-parse', '--show-toplevel')).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {'status': 'not_git_install'}
    if top != ROOT:
        return {'status': 'requires_standalone_git_install'}
    if git('status', '--porcelain', '--untracked-files=all'):
        return {'status': 'local_changes_preserved'}
    if normalize(git('config', '--get', 'remote.origin.url')) != normalize(remote):
        return {'status': 'repository_mismatch'}
    old = git('rev-parse', 'HEAD')
    # Back off failed checks as well: offline users must not wait on every task.
    try:
        git('fetch', '--no-tags', 'origin', branch)
    except (subprocess.SubprocessError, OSError) as exc:
        marker.touch()
        return {'status': 'offline_current_version_preserved', 'error_type': type(exc).__name__}
    target = git('rev-parse', 'FETCH_HEAD')
    if target == old:
        marker.touch()
        return {'status': 'up_to_date'}
    git('merge-base', '--is-ancestor', old, target)
    # Test the exact fetched commit in a disposable checkout, before activation.
    with tempfile.TemporaryDirectory(prefix='imagegen-update-') as temp:
        git('clone', '--quiet', '--no-hardlinks', str(ROOT), temp)
        git('fetch', str(ROOT), target, cwd=temp)
        git('checkout', '--quiet', '--detach', target, cwd=temp)
        candidate = Path(temp)
        if (candidate / 'requirements.txt').read_bytes() != (ROOT / 'requirements.txt').read_bytes():
            return {'status': 'dependency_change_requires_manual_upgrade'}
        for required in ['SKILL.md', 'README.md', 'version.json', 'release.json', 'requirements.txt',
                         'scripts/client.py', 'scripts/install.py', 'scripts/update.py',
                         'scripts/ask_capability.py', 'scripts/offline_test.py']:
            if not (candidate / required).is_file():
                raise ValueError('invalid_release_layout')
        json.loads((candidate / 'version.json').read_text(encoding='utf-8'))
        smoke(candidate)
        subprocess.run([sys.executable, '-B', 'scripts/offline_test.py'], cwd=temp, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=45)
    if git('rev-parse', 'HEAD') != old or git('status', '--porcelain', '--untracked-files=all'):
        return {'status': 'installation_changed_during_check'}
    git('update-ref', 'refs/imagegen-dual/previous', old)
    git('merge', '--ff-only', target)
    try:
        smoke(ROOT)
    except Exception:
        if git('rev-parse', 'HEAD') == target and not git('status', '--porcelain', '--untracked-files=all'):
            git('reset', '--hard', old)
            return {'status': 'rolled_back_after_startup_failure', 'commit': old}
        return {'status': 'startup_failed_local_changes_preserved', 'previous_commit': old}
    marker.touch()
    return {'status': 'updated', 'previous_commit': old, 'commit': target}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(update(args.auto)))
    except Exception as exc:
        print(json.dumps({'status': 'update_skipped', 'error_type': type(exc).__name__}))
