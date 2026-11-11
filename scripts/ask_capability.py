"""Store non-secret native-ask capability results by exact client/model route."""
import argparse
import json
from pathlib import Path
import time

STATE = Path.home() / '.imagegen-dual'
CACHE = STATE / 'ask-capabilities.json'
FIELDS = ('host', 'client', 'model', 'gateway', 'protocol', 'tool', 'version')
STATUSES = ('supported', 'unsupported', 'text_fallback')


def clean(value):
    return str(value or 'unknown').strip()[:160]


def identity(args):
    values = {name: clean(getattr(args, name)) for name in FIELDS}
    return values, ':'.join(values[name].lower() for name in FIELDS)


def load():
    try:
        data = json.loads(CACHE.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def show(args):
    values, key = identity(args)
    result = load().get(key)
    return {'key': key, 'dimensions': values, 'status': result['status'] if result else 'untested',
            'record': result}


def record(args):
    if args.status not in STATUSES:
        raise ValueError('invalid_status')
    values, key = identity(args)
    data = load()
    data[key] = {
        **values,
        'status': args.status,
        'checked_at': time.time(),
        'evidence': args.evidence
    }
    STATE.mkdir(parents=True, exist_ok=True)
    temporary = CACHE.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(CACHE)
    return {'key': key, 'status': args.status}


def parser():
    common = argparse.ArgumentParser(add_help=False)
    for name in FIELDS:
        common.add_argument('--' + name, default='unknown')
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('show', parents=[common])
    write = sub.add_parser('record', parents=[common])
    write.add_argument('--status', required=True, choices=STATUSES)
    write.add_argument('--evidence', required=True,
                       choices=('click_selected', 'unsupported_call', 'user_preferred_text'))
    return p


if __name__ == '__main__':
    args = parser().parse_args()
    try:
        result = record(args) if args.command == 'record' else show(args)
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__}))
        raise SystemExit(1)
