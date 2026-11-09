"""Installation GET checks only. Never generates images or loads other profiles."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import time
import hashlib
from pathlib import Path
import client as c


def probe(base, key):
    start = time.monotonic()
    result = {'endpoint': base, 'method': 'GET', 'path': '/models'}
    try:
        with c.session() as s:
            r = s.get(base + '/models', headers={'Authorization': 'Bearer ' + key}, timeout=(4, 8), allow_redirects=False)
        result['http_status'] = r.status_code
        if r.status_code == 200:
            result['model_count'] = len(r.json()['data'])
            result['status'] = 'success'
        else:
            result.update(status='failed', error=c.error_detail(r, key))
    except Exception as exc:
        result.update(status='failed', error_type=type(exc).__name__, message=c.safe(exc, key))
    result['elapsed_seconds'] = round(time.monotonic() - start, 3)
    return result


def run(profile=None):
    cfg, key, bases = c.load(profile)
    # Three serial GETs and a bounded two-request concurrent GET per endpoint.
    reports = []
    for base in bases:
        serial = [probe(base, key) for _ in range(3)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            concurrent = list(pool.map(lambda _: probe(base, key), range(2)))
        reports.append({'endpoint': base, 'serial': serial, 'concurrent': concurrent})
    result = {'profile': cfg['selected_profile'], 'generation_posts': 0, 'reports': reports,
            'scope': 'models_GET_connectivity_only_not_image_concurrency_or_billing_proof'}
    version = json.loads((Path(__file__).resolve().parents[1] / 'version.json').read_text(encoding='utf-8'))['version']
    identity = hashlib.sha256(json.dumps([version, cfg['selected_profile'], bases]).encode()).hexdigest()[:20]
    directory = c.STATE / 'acceptance'
    directory.mkdir(parents=True, exist_ok=True)
    result.update(version=version, checked_at=time.time())
    (directory / (identity + '.json')).write_text(json.dumps(result, ensure_ascii=True, indent=2), encoding='utf-8')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--profile')
    args = p.parse_args()
    try:
        print(json.dumps(run(args.profile), ensure_ascii=True, indent=2))
    except c.SelectionRequired as exc:
        print(json.dumps({'status': 'selection_required', 'field': exc.field, 'options': exc.options}))
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__, 'message': c.safe(exc)}))
