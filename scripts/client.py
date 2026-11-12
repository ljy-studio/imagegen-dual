"""Portable text-to-image client. Never retries ambiguous POST outcomes."""
import argparse
import base64
import hashlib
import io
import json
import os
import re
from pathlib import Path
import time
from urllib.parse import urlparse
import uuid
import accounts
from runtime import ROOT

import requests
from PIL import Image

STATE = Path.home() / '.imagegen-dual'
DIRECT = ['https://api.gaoxin.net.cn/v1', 'https://api-sh.gaoxin.net.cn/v1']


def safe(value, key=None):
    text = str(value)
    if key:
        text = text.replace(key, '[REDACTED]')
    text = re.sub(r'https?://[^\s"<>]+', '[URL REDACTED]', text)
    text = re.sub(r'(?i)(bearer\s+|sk-)[A-Za-z0-9_.-]+', '[REDACTED]', text)
    return text[:2000]


def error_detail(response, key):
    try:
        data = response.json()
        error = data.get('error', data)
        if isinstance(error, dict):
            details = {k: safe(error[k], key) for k in ('message', 'code', 'type', 'param') if k in error}
        else:
            details = {'message': safe(error, key)}
    except (ValueError, AttributeError):
        details = {'message': safe(getattr(response, 'text', 'non_json_response'), key)}
    details['http_status'] = response.status_code
    details['request_id'] = safe(response.headers.get('x-request-id', response.headers.get('request-id', 'unknown')), key)
    return details


class RouteError(ValueError):
    def __init__(self, attempts):
        self.attempts = attempts


def session():
    s = requests.Session()
    s.trust_env = False  # No implicit proxy credentials/netrc or SDK retries.
    return s


class SelectionRequired(ValueError):
    def __init__(self, field, options):
        self.field, self.options = field, options


def profiles(cfg):
    if 'profiles' not in cfg:
        return {'default': cfg}
    result = cfg['profiles']
    if not isinstance(result, dict) or not result:
        raise ValueError('profiles_required')
    return result


def load(profile=None):
    path = STATE / 'config.json'
    cfg = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    choices = profiles(cfg) if cfg else {}
    discovered, _ = accounts.discover()
    choices.update({ref: {'account_ref': ref} for ref in discovered})
    if profile is None:
        raise SelectionRequired('profile', list(choices))
    if profile not in choices:
        raise ValueError('unknown_profile')
    cfg = dict(choices[profile], selected_profile=profile)
    if cfg.get('account_ref'):
        selected, _ = accounts.discover(selected=cfg['account_ref'])
        key = selected.get(cfg['account_ref'], {}).get('key')
    else:
        key = os.environ.get(cfg.get('key_env', 'IMAGEGEN_API_KEY'))
    if not key:
        raise ValueError('missing_key_environment_variable')
    bases = [cfg['gateway_url']] if cfg.get('gateway_url') else DIRECT
    normalized = []
    for base in bases:
        u = urlparse(base)
        if u.username or u.password or u.query or u.fragment:
            raise ValueError('invalid_base_url')
        if u.scheme != 'https' and not (u.scheme == 'http' and u.hostname in ('localhost', '127.0.0.1', '::1')):
            raise ValueError('https_or_loopback_required')
        normalized.append(base.rstrip('/') if u.path.rstrip('/').endswith('/v1') else base.rstrip('/') + '/v1')
    return cfg, key, normalized


def routes(key, bases):
    """Probe primary first. Never infer a POST is safe from a GET result."""
    result = []
    cache_id = hashlib.sha256('|'.join(bases).encode()).hexdigest()[:20]
    cache_file = STATE / ('route-' + cache_id + '.json')
    try:
        cached = json.loads(cache_file.read_text(encoding='utf-8'))
        if time.time() - cached['time'] < 600 and cached['endpoint'] in bases:
            bases = [cached['endpoint']] + [b for b in bases if b != cached['endpoint']]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    failures = []
    for base in bases:
        try:
            with session() as s:
                r = s.get(base + '/models', headers={'Authorization': 'Bearer ' + key}, timeout=(4, 8), allow_redirects=False)
            if r.status_code == 200:
                data = r.json()['data']
                ids = [x['id'] for x in data if isinstance(x.get('id'), str)]
                result.append({'endpoint': base, 'models': ids})
            else:
                failures.append(dict(endpoint=base, **error_detail(r, key)))
        except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
            failures.append({'endpoint': base, 'error_type': type(exc).__name__, 'message': safe(exc, key)})
            continue
    if not result:
        raise RouteError(failures)
    try:
        STATE.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({'time': time.time(), 'endpoint': result[0]['endpoint']}), encoding='utf-8')
    except OSError:
        pass
    return result


def validate(raw):
    with Image.open(io.BytesIO(raw)) as im:
        im.verify()
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        fmt, size = im.format, im.size
    if fmt not in ('PNG', 'JPEG', 'WEBP'):
        raise ValueError('unsupported_image_format')
    return {'format': fmt, 'width': size[0], 'height': size[1], 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def artifact(task, response):
    item = response['data'][0]
    if item.get('url'):
        if urlparse(item['url']).scheme != 'https':
            raise ValueError('image_url_requires_https')
        # Separate session: never forward API authorization to storage.
        with session() as s:
            r = s.get(item['url'], timeout=(10, 120))
            r.raise_for_status()
            raw = r.content
    else:
        raw = base64.b64decode(item['b64_json'], validate=True)
    info = validate(raw)
    ext = {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[info['format']]
    path = task / ('image-' + uuid.uuid4().hex + '.' + ext)
    path.write_bytes(raw)
    return {'status': 'success', 'path': str(path), 'validation': info}


def generate(job, key, available, operation='generate'):
    model = job.get('model')
    if not isinstance(model, str) or not model.strip():
        raise SelectionRequired('model', sorted({m for x in available for m in x['models']}))
    eligible = [x['endpoint'] for x in available if model in x['models']]
    if not eligible:
        raise ValueError('requested_model_unavailable_choose_from_models')
    if not isinstance(job.get('prompt'), str) or not job['prompt'].strip():
        raise ValueError('prompt_required')
    image = Path(job['image']).resolve() if operation == 'edit' else None
    image_info = validate(image.read_bytes()) if image else None
    transport = job.get('edit_transport', 'json') if image else 'json'
    if transport not in ('json', 'multipart'):
        raise ValueError('edit_transport_must_be_json_or_multipart')
    image_data = None
    if image:
        mime = {'PNG': 'image/png', 'JPEG': 'image/jpeg', 'WEBP': 'image/webp'}[image_info['format']]
        if transport == 'json':
            image_data = 'data:' + mime + ';base64,' + base64.b64encode(image.read_bytes()).decode('ascii')
            if len(image_data) > 20971520:
                raise ValueError('edit_data_url_exceeds_20MiB_choose_supported_multipart')
        elif image_info['bytes'] >= 50 * 1024 * 1024:
            raise ValueError('edit_file_must_be_less_than_50MiB')
    task = Path(job.get('output_dir', 'outputs/imagegen')).resolve() / uuid.uuid4().hex
    task.mkdir(parents=True)
    record = {'status': 'started', 'operation': operation, 'task': str(task), 'request_model': model, 'response_model': None, 'attempts': []}
    record.update(request_content_type='application/json' if transport == 'json' else 'multipart/form-data',
                  request_path='/images/edits' if image else '/images/generations')
    (task / 'record.json').write_text(json.dumps(record), encoding='utf-8')
    start = time.monotonic()
    try:
        for base in eligible:
            record['endpoint'] = base
            record['attempts'].append(base)
            try:
                with session() as s:
                    payload = {'prompt': job['prompt'], 'model': model, 'n': 1,
                               'size': job.get('size', '1024x1024'), 'quality': job.get('quality', 'auto')}
                    args = {'headers': {'Authorization': 'Bearer ' + key}, 'timeout': (10, 360), 'allow_redirects': False}
                    if image and transport == 'multipart':
                        with image.open('rb') as stream:
                            r = s.post(base + '/images/edits', data=payload, files={'image': (image.name, stream, mime)}, **args)
                    elif image:
                        payload['images'] = [{'image_url': image_data}]
                        r = s.post(base + '/images/edits', json=payload, **args)
                    else:
                        r = s.post(base + '/images/generations', json=payload, **args)
            except requests.ConnectTimeout as exc:
                record['error'] = {'error_type': type(exc).__name__, 'message': safe(exc, key)}
                record['status'] = 'connection_not_established'
                if job.get('no_fallback'):
                    break
                continue
            except requests.RequestException as exc:
                record['error'] = {'error_type': type(exc).__name__, 'message': safe(exc, key)}
                record['status'] = 'result_unknown'
                break
            record['http_status'] = r.status_code
            if r.status_code != 200:
                record['error'] = error_detail(r, key)
                if image and 'numeric literal' in record['error'].get('message', ''):
                    record['diagnosis'] = 'Possible request encoding/parser mismatch; verify gateway Content-Type handling. No retry sent.'
                record['status'] = ('rejected' if r.status_code in (400, 401, 402, 403, 404, 422, 429) else 'result_unknown')
                if r.status_code == 429:
                    record['retry_after'] = r.headers.get('Retry-After')
                break
            try:
                response = r.json()
                record['response_model'] = response.get('model')
                (task / 'response.json').write_text(json.dumps(response), encoding='utf-8')
                if not response.get('data'):
                    record['error'] = error_detail(r, key)
                    record['status'] = 'result_unknown'
                    break
            except (ValueError, AttributeError):
                record['status'] = 'result_unknown'
                break
            record['status'] = 'artifact_failed'
            record.update(artifact(task, response))
            record.pop('error', None)
            break
    except Exception as exc:
        record['error_type'] = type(exc).__name__
        record['error_message'] = safe(exc, key)
        if record['status'] == 'started':
            record['status'] = 'result_unknown'
    finally:
        record['elapsed_seconds'] = round(time.monotonic() - start, 3)
        (task / 'record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['profiles', 'models', 'generate', 'edit', 'resume', 'status', 'diagnose'])
    p.add_argument('--profile')
    p.add_argument('--job')
    p.add_argument('--task')
    a = p.parse_args()
    try:
        if a.command == 'profiles':
            path = STATE / 'config.json'
            manual = profiles(json.loads(path.read_text(encoding='utf-8'))) if path.exists() else {}
            found, notices = accounts.discover()
            result = {'profiles': {**{k: {'label': k, 'source': 'manual'} for k in manual}, **found}, 'notices': notices}
        elif a.command in ('status', 'diagnose'):
            from diagnostics import report
            result = report(Path(a.task).resolve(), share=a.command == 'diagnose')
        elif a.command == 'resume':
            task = Path(a.task).resolve()
            result = artifact(task, json.loads((task / 'response.json').read_text(encoding='utf-8')))
            record = json.loads((task / 'record.json').read_text(encoding='utf-8'))
            record.update(result)
            (task / 'record.json').write_text(json.dumps(record), encoding='utf-8')
        else:
            job = json.loads(Path(a.job).read_text(encoding='utf-8-sig')) if a.command in ('generate', 'edit') else {}
            if a.profile and job.get('profile') and a.profile != job['profile']:
                raise ValueError('conflicting_profile_selection')
            cfg, key, bases = load(a.profile or job.get('profile'))
            available = routes(key, bases)
            if a.command == 'models':
                catalog = json.loads((ROOT / 'capabilities.json').read_text(encoding='utf-8'))
                result = {'profile': cfg['selected_profile'], 'routes': available,
                          'image_models': {m: catalog['models'][m] for m in sorted({m for x in available for m in x['models']}) if m in catalog['models']}}
            else:
                if a.command == 'edit':
                    job.setdefault('edit_transport', cfg.get('edit_transport', 'json'))
                result = generate(job, key, available, a.command)
            result['profile'] = cfg['selected_profile']
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except SelectionRequired as exc:
        print(json.dumps({'status': 'selection_required', 'field': exc.field, 'options': exc.options}, ensure_ascii=True))
        raise SystemExit(2)
    except RouteError as exc:
        print(json.dumps({'status': 'failed', 'stage': 'models', 'errors': exc.attempts}, ensure_ascii=True))
        raise SystemExit(1)
    except Exception as exc:
        # Exceptions from HTTP libraries may contain signed URLs. Never print them.
        print(json.dumps({'status': 'failed', 'error_type': type(exc).__name__, 'message': safe(exc, locals().get('key'))}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
