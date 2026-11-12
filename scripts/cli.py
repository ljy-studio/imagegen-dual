"""One entry point shared by source and portable distributions."""
import io
import json
import sys
import client
from runtime import ROOT


def self_test():
    data = io.BytesIO()
    client.Image.new('RGB', (4, 4)).save(data, format='PNG')
    assert client.validate(data.getvalue())['width'] == 4
    assert 'secret' not in client.safe('secret', 'secret')
    for name in ('version.json', 'release.json', 'capabilities.json'):
        json.loads((ROOT / name).read_text(encoding='utf-8'))
    return {'status': 'success', 'scope': 'offline_runtime_check', 'network_requests': 0}


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else '--help'
    if command == 'self-test':
        print(json.dumps(self_test()))
    elif command == 'install':
        import install
        print(json.dumps(install.initialize(skip_deps='--skip-deps' in sys.argv, archive='--archive' in sys.argv)))
    elif command == 'update':
        import update
        print(json.dumps(update.update(auto='--auto' in sys.argv)))
    else:
        client.main()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__, 'message': client.safe(exc)}))
        raise SystemExit(1)
