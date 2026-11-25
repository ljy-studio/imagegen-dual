"""Local drawing preferences and short-lived account-scoped discovery results."""
import hashlib
import json
import time
import uuid


def read(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix("." + uuid.uuid4().hex + ".tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def resolve(job, preference, field):
    if preference and job.get(field, preference[field]) == preference[field]:
        job.setdefault(field, preference[field])
        job.setdefault("model", preference["model"])


def cache_path(root, account, bases, key):
    scope = json.dumps([account, bases, key]).encode()
    return root / ("models-" + hashlib.sha256(scope).hexdigest() + ".json")


def discovery(path, fetch, fresh=False):
    cached = read(path)
    if not fresh and 0 <= time.time() - cached.get("time", 0) < 600 and cached.get("routes"):
        return cached["routes"]
    result = fetch()
    try:
        write(path, {"time": time.time(), "routes": result})
    except OSError:
        pass
    return result
