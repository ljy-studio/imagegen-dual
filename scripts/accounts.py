"""Read-only discovery of configured API providers; never imports OAuth logins."""
import contextlib
import json
from pathlib import Path
import sqlite3
import tomllib
from urllib.parse import urlparse

HOSTS = {'api.gaoxin.net.cn', 'api-sh.gaoxin.net.cn'}


def supported(url):
    u = urlparse(url)
    return u.hostname in HOSTS and u.scheme == 'https' and not u.username and not u.password


def base_url(provider):
    """Resolve a magpie provider's API base URL.

    Real magpie records store baseAPI as the name of another field (for example
    "responses") that holds the URL, not the URL itself. Fall back to the raw
    value so a plain-URL schema keeps working.
    """
    value = provider.get('baseAPI', '')
    if isinstance(value, str) and value and value != 'baseAPI':
        target = provider.get(value)
        if isinstance(target, str) and target:
            return target
    return value


def discover(home=None, selected=None):
    home = Path(home or Path.home())
    results, notices = {}, []
    db = home / '.cc-switch/cc-switch.db'
    if db.exists():
        try:
            with contextlib.closing(sqlite3.connect(db.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
                for pid, app, name, raw in conn.execute('select id,app_type,name,settings_config from providers'):
                    ref = 'ccswitch:' + str(app) + ':' + str(pid)
                    if selected and selected != ref:
                        continue
                    try:
                        data = json.loads(raw)
                        conf = tomllib.loads(data['config']) if isinstance(data.get('config'), str) else {}
                        env = data.get('env', {})
                        urls = [p.get('base_url', '') for p in conf.get('model_providers', {}).values()]
                        urls += [env.get('ANTHROPIC_BASE_URL', ''), env.get('OPENAI_BASE_URL', '')]
                        if not any(supported(url) for url in urls):
                            continue
                        item = {'label': str(name) + ' (' + str(app) + ')', 'source': 'ccswitch'}
                        if selected:
                            key = data.get('auth', {}).get('OPENAI_API_KEY') or env.get('ANTHROPIC_AUTH_TOKEN') or env.get('OPENAI_API_KEY')
                            if not isinstance(key, str) or not key.strip():
                                raise ValueError('selected_api_key_missing')
                            item['key'] = key
                        results[ref] = item
                    except (ValueError, TypeError, AttributeError):
                        notices.append({'source': 'ccswitch', 'status': 'unsupported_provider_record'})
        except (sqlite3.Error, OSError):
            notices.append({'source': 'ccswitch', 'status': 'database_unavailable_or_schema_unsupported'})
    path = home / '.config/magpie/providers.json'
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            for p in data['providers']:
                ref = 'magpie:' + str(p['id'])
                if selected and selected != ref:
                    continue
                if not supported(base_url(p)):
                    continue
                item = {'label': str(p['name']), 'source': 'magpie'}
                if selected:
                    if not isinstance(p.get('key'), str) or not p['key'].strip():
                        raise ValueError('selected_api_key_missing')
                    item['key'] = p['key']
                results[ref] = item
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            notices.append({'source': 'magpie', 'status': 'providers_unavailable_or_schema_unsupported'})
    return results, notices
