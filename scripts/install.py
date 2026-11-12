"""Initialize a cloned imagegen-dual skill without storing API credentials."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from runtime import ROOT, BUNDLED
if not BUNDLED:
    ROOT = Path(__file__).resolve().parents[1]

STATE = Path.home() / '.imagegen-dual'


def run(*args, cwd=ROOT, quiet=False):
    return subprocess.run(args, cwd=cwd, check=True, text=True,
                          stdout=subprocess.DEVNULL if quiet else None,
                          stderr=subprocess.STDOUT if quiet else None)


def normalize(url):
    return url.strip().removesuffix('.git').rstrip('/')


def verify_migration(backup):
    if not backup:
        raise ValueError("preinstall_migration_required_use_migrate_scan_then_apply")
    from migrate import direct, sha
    path = direct(backup)
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "applied" or manifest.get("schema") != 1:
        raise ValueError("migration_receipt_not_applied")
    if str(ROOT.resolve().parent) not in manifest.get("skills_roots", []):
        raise ValueError("install_target_not_in_migration_scope")
    for item in manifest["skills"]:
        old = direct(item["path"])
        if old != ROOT.resolve() and old.exists():
            raise ValueError("old_skill_reappeared_after_cleanup")
    for item in manifest["rules"]:
        if sha(direct(item["path"]).read_bytes()) != item["after"]:
            raise ValueError("rules_changed_after_cleanup_review_again")
    return str(path)


def initialize(skip_deps=False, archive=False, migration_backup=None):
    if ROOT.name != "imagegen-dual":
        raise ValueError("installation_directory_must_be_imagegen-dual")
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8-sig")
    if "name: imagegen-dual" not in skill.split("---", 2)[1].splitlines():
        raise ValueError("skill_identifier_must_be_imagegen-dual")
    ui = (ROOT / "agents/openai.yaml").read_text(encoding="utf-8")
    if '  display_name: "imagegen dual"' not in ui.splitlines():
        raise ValueError("display_name_must_be_imagegen_dual")
    receipt = verify_migration(migration_backup)
    if sys.version_info < (3, 11):
        raise ValueError('python_3_11_or_newer_required')
    release = json.loads((ROOT / 'release.json').read_text(encoding='utf-8'))
    archive = archive or BUNDLED
    commit = None
    if not archive:
        top_path = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], cwd=ROOT,
                                           text=True, encoding="utf-8", stderr=subprocess.DEVNULL).strip()
        if Path(top_path).resolve() != ROOT:
            raise ValueError('standalone_git_checkout_required_or_use_archive')
        remote = subprocess.check_output(['git', 'config', '--get', 'remote.origin.url'], cwd=ROOT,
                                         text=True, stderr=subprocess.DEVNULL).strip()
        if normalize(remote) != normalize(release['repository']):
            raise ValueError('trusted_release_repository_mismatch')
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if BUNDLED:
        from cli import self_test
        self_test()
        skip_deps = True
    if not skip_deps:
        if sys.prefix == sys.base_prefix:
            raise ValueError('use_private_venv_or_portable_package_no_global_pip')
        run(sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt')
    if not BUNDLED:
        run(sys.executable, '-B', 'scripts/offline_test.py', quiet=True)
    version = json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))['version']
    STATE.mkdir(parents=True, exist_ok=True)
    state = {
        'version': version,
        'mode': 'portable' if BUNDLED else ('archive' if archive else 'git'),
        'root': str(ROOT),
        'display_name': 'imagegen dual',
        'migration_backup': receipt,
        'commit': commit,
        'repository': release['repository'],
        'installed_at': time.time(),
        'python': sys.version.split()[0]
    }
    (STATE / 'install.json').write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    return state


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-deps', action='store_true')
    parser.add_argument('--archive', action='store_true', help='Initialize a verified archive; no Git or automatic source updates')
    parser.add_argument('--migration-backup', required=True, help='Applied preinstall cleanup receipt directory')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(initialize(args.skip_deps, args.archive, args.migration_backup), ensure_ascii=True, indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__,
                          'message': str(exc)[:500]}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
