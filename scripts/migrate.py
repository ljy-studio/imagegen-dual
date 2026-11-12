"""Reviewed, reversible cleanup before installing imagegen-dual.

Inventory never removes by keyword. Apply only an agent-reviewed plan containing
exact skill directories and exact rule text, with snapshot hashes to reject drift.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import uuid
from runtime import ROOT

STATE = Path.home() / '.imagegen-dual'
RULE_NAMES = {'agent.md', 'agents.md'}
KINDS = {'old_imagegen_dual', 'external_image_api_only'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def direct(path):
    path = Path(path).expanduser().absolute()
    for parent in (path, *path.parents):
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('linked_path_requires_manual_review')
    return path.resolve()


def fingerprint(path):
    path = direct(path)
    digest = hashlib.sha256()
    for item in sorted(path.rglob('*')):
        direct(item)
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode())
            digest.update(b'\0')
            digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def inventory(roots, rules):
    roots = sorted({str(direct(p)) for p in roots})
    files = sorted({str(direct(p)) for p in rules})
    items = []
    for root in roots:
        base = Path(root)
        if not base.is_dir():
            raise ValueError('skills_root_missing')
        for directory in sorted(base.iterdir()):
            if not directory.is_dir() or not (directory / 'SKILL.md').is_file():
                continue
            try:
                path = direct(directory)
                if path == ROOT.resolve():
                    continue
                content = (path / 'SKILL.md').read_text(encoding='utf-8-sig')
                front = content.split('---', 2)[1] if content.startswith('---') else ''
                items.append({'path': str(path), 'sha256': fingerprint(path),
                              'metadata': front.strip(), 'decision': 'review_required'})
            except (ValueError, OSError, UnicodeError) as exc:
                items.append({'path': str(directory), 'decision': 'manual_review', 'reason': type(exc).__name__})
    rule_items = []
    for name in files:
        path = Path(name)
        if path.name.lower() not in RULE_NAMES or not path.is_file():
            raise ValueError('explicit_AGENT_or_AGENTS_file_required')
        rule_items.append({'path': name, 'sha256': sha(path.read_bytes()), 'remove_text': []})
    return {'schema': 1, 'reviewed': False, 'skills_roots': roots, 'rule_files': files,
            'inventory': items, 'remove_skills': [], 'edit_rules': rule_items}


def preflight(plan):
    if plan.get('schema') != 1 or plan.get('reviewed') is not True:
        raise ValueError('reviewed_migration_plan_required')
    roots = {direct(p) for p in plan['skills_roots']}
    rules = {direct(p) for p in plan['rule_files']}
    selected, edits, seen = [], [], set()
    for item in plan['remove_skills']:
        path = direct(item['path'])
        if path in seen or path.parent not in roots or not (path / 'SKILL.md').is_file():
            raise ValueError('skill_outside_reviewed_root_or_duplicate')
        if path == ROOT.resolve() or ROOT.resolve().is_relative_to(path):
            raise ValueError('cannot_remove_running_installer')
        if item.get('kind') not in KINDS or not str(item.get('reason', '')).strip():
            raise ValueError('skill_purpose_review_required')
        if fingerprint(path) != item['sha256']:
            raise ValueError('skill_changed_since_review')
        seen.add(path)
        selected.append((path, item['sha256']))
    for item in plan['edit_rules']:
        path = direct(item['path'])
        if path not in rules or path.name.lower() not in RULE_NAMES or path in seen:
            raise ValueError('rule_outside_reviewed_scope_or_duplicate')
        if any(path.is_relative_to(skill) for skill, _ in selected):
            raise ValueError('rule_inside_removed_skill')
        old = path.read_bytes()
        if sha(old) != item['sha256']:
            raise ValueError('rule_changed_since_review')
        text = old.decode('utf-8')  # Preserve UTF-8 BOM and CRLF byte-for-byte.
        spans = []
        for block in item['remove_text']:
            if not isinstance(block, str) or not block.strip() or text.count(block) != 1:
                raise ValueError('rule_text_not_unique_or_missing')
            start = text.index(block)
            spans.append((start, start + len(block)))
        spans.sort()
        if any(b > c for (_, b), (c, _) in zip(spans, spans[1:])):
            raise ValueError('overlapping_rule_selections')
        for start, end in reversed(spans):
            text = text[:start] + text[end:]
        if spans:
            edits.append((path, old, text.encode('utf-8')))
        seen.add(path)
    return selected, edits, roots


def write_bytes(path, raw):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        tmp.write_bytes(raw)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def apply(plan, state=None):
    selected, edits, roots = preflight(plan)
    base = direct(state or STATE) / 'migration-backups'
    if any(base.is_relative_to(root) or root.is_relative_to(base) for root in roots):
        raise ValueError('backup_must_be_outside_skill_discovery_roots')
    backup = base / uuid.uuid4().hex
    backup.mkdir(parents=True, mode=0o700)
    manifest = {'schema': 1, 'status': 'preparing', 'skills': [], 'rules': [],
                'skills_roots': sorted(str(p) for p in roots),
                'rule_files': plan['rule_files']}
    journal = backup / 'manifest.json'

    def save():
        write_bytes(journal, json.dumps(manifest, ensure_ascii=False, indent=2).encode())

    # All rule backups complete before any source is changed.
    for index, (path, old, new) in enumerate(edits):
        copy = backup / ('rule-' + str(index) + '.bin')
        copy.write_bytes(old)
        manifest['rules'].append({'path': str(path), 'backup': copy.name,
                                  'before': sha(old), 'after': sha(new)})
    for index, (path, digest) in enumerate(selected):
        manifest['skills'].append({'path': str(path), 'backup': 'skill-' + str(index), 'sha256': digest})
    save()
    changed_rules, moved = [], []
    try:
        for item in manifest['skills']:
            path = direct(item['path'])
            if fingerprint(path) != item['sha256']:
                raise ValueError('skill_changed_during_migration')
            shutil.move(str(path), str(backup / item['backup']))
            moved.append(item)
        for (path, old, new), item in zip(edits, manifest['rules']):
            if path.read_bytes() != old:
                raise ValueError('rule_changed_during_migration')
            write_bytes(path, new)
            changed_rules.append(item)
        manifest['status'] = 'applied'
        save()
    except Exception:
        for item in reversed(changed_rules):
            write_bytes(Path(item['path']), (backup / item['backup']).read_bytes())
        for item in reversed(moved):
            shutil.move(str(backup / item['backup']), item['path'])
        manifest['status'] = 'rolled_back'
        save()
        raise
    return {'status': 'migration_complete', 'backup': str(backup),
            'removed_skills': len(selected), 'edited_rule_files': len(edits)}


def restore(backup):
    backup = direct(backup)
    path = backup / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest['status'] != 'applied':
        raise ValueError('migration_not_applied')
    for item in manifest['skills']:
        destination = direct(item['path'])
        if destination.exists():
            raise ValueError('restore_destination_exists_move_new_install_first')
        source = direct(backup / item['backup'])
        if source.parent != backup or fingerprint(source) != item['sha256']:
            raise ValueError('backup_skill_changed')
    for item in manifest['rules']:
        source = direct(backup / item['backup'])
        if source.parent != backup or sha(source.read_bytes()) != item['before']:
            raise ValueError('backup_rule_changed')
        if sha(direct(item['path']).read_bytes()) != item['after']:
            raise ValueError('rule_modified_after_migration_preserved')
    for item in manifest['rules']:
        write_bytes(Path(item['path']), (backup / item['backup']).read_bytes())
    for item in manifest['skills']:
        shutil.move(str(backup / item['backup']), item['path'])
    manifest['status'] = 'restored'
    write_bytes(path, json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    return {'status': 'restored', 'backup': str(backup)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    scan = commands.add_parser('scan')
    scan.add_argument('--skills-root', action='append', required=True)
    scan.add_argument('--rules', action='append', default=[])
    scan.add_argument('--output', required=True)
    use = commands.add_parser('apply')
    use.add_argument('--plan', required=True)
    undo = commands.add_parser('restore')
    undo.add_argument('--backup', required=True)
    args = parser.parse_args(argv)
    if args.command == 'scan':
        result = inventory(args.skills_root, args.rules)
        target = Path(args.output).expanduser().absolute()
        roots = [Path(x) for x in result['skills_roots']]
        if any(target.is_relative_to(r) for r in roots):
            raise ValueError('plan_must_be_outside_skill_roots')
        # Never overwrite source data through an output flag.
        with target.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
        result = {'status': 'review_required', 'plan': str(target), 'skills': result['inventory']}
    elif args.command == 'apply':
        result = apply(json.loads(Path(args.plan).read_text(encoding='utf-8-sig')))
    else:
        result = restore(args.backup)
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()

