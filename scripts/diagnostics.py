"""Allowlisted support report: never exports response bodies, prompts or account names."""
import json
from pathlib import Path
import platform
from urllib.parse import urlparse

STATUSES = {
    'started': 'Request may have been sent; outcome unknown. Do not resubmit automatically.',
    'result_unknown': 'Outcome and billing unknown. Ask support using request ID; do not resubmit.',
    'connection_not_established': 'Connection was not established.',
    'rejected': 'Server rejected the request. Check HTTP status and error locally.',
    'artifact_failed': 'Response received but image saving failed. Resume existing response only.',
    'success': 'Image saved and decoded successfully.',
}


def report(task, share=False):
    record = json.loads((task / 'record.json').read_text(encoding='utf-8'))
    if not share:
        return {'record': record, 'next_step': STATUSES.get(record.get('status'), 'Inspect local record before proceeding.')}
    version = json.loads((Path(__file__).resolve().parents[1] / 'version.json').read_text(encoding='utf-8'))['version']
    result = {k: record[k] for k in ('status', 'operation', 'http_status', 'elapsed_seconds') if k in record}
    result.update(version=version, python=platform.python_version(), system=platform.system(),
                  next_step=STATUSES.get(record.get('status'), 'Inspect locally.'))
    host = urlparse(record.get('endpoint', '')).hostname
    result['route'] = host if host in ('api.gaoxin.net.cn', 'api-sh.gaoxin.net.cn') else 'gateway_or_unknown'
    # Server text, codes, IDs, model IDs and provider labels may echo private input.
    # They remain in local record. Add manually only after user review.
    result['server_details'] = 'Excluded; review local error and request ID before sharing.'
    return result
