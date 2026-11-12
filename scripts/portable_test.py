"""Exercise the extracted portable package against a loopback fake API only."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import shutil
import threading
import zipfile
from PIL import Image


def verify(archive):
    raw = io.BytesIO()
    Image.new('RGB', (4, 4), 'blue').save(raw, format='PNG')
    encoded = base64.b64encode(raw.getvalue()).decode('ascii')
    models = ['gpt-image-2.5-flare', 'gpt-image-2.5-sunburst']
    posts = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, data):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.respond(200, {'data': [{'id': m} for m in models]})

        def do_POST(self):
            body = self.rfile.read(int(self.headers['Content-Length']))
            try:
                assert self.path == '/v1/images/edits'
                assert self.headers['Content-Type'] == 'application/json'
                data = json.loads(body)
                assert data['model'] in models
                assert data['images'][0]['image_url'] == 'data:image/png;base64,' + encoded
                assert data['n'] == 1
                posts.append(data['model'])
                self.respond(200, {'data': [{'b64_json': encoded}], 'model': data['model']})
            except Exception as exc:
                self.respond(400, {'error': {'message': type(exc).__name__}})

    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp).resolve()
        with zipfile.ZipFile(archive) as z:
            for item in z.namelist():
                if not (root / item).resolve().is_relative_to(root.resolve()):
                    raise ValueError('unsafe_archive_member')
            z.extractall(root)
        skill = root / 'imagegen-dual'
        exe = skill / 'imagegen-dual.exe'
        home = root.parent / (root.name + '-isolated-home')
        state = home / '.imagegen-dual'
        state.mkdir(parents=True)
        env = dict(os.environ, USERPROFILE=str(home), HOME=str(home),
                   PATH=os.path.join(os.environ['SystemRoot'], 'System32'),
                   TEST_GATEWAY_KEY='offline-test-key')
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)

        def run(*args):
            output = subprocess.check_output([str(exe), *args], cwd=skill, env=env,
                                             text=True, encoding='utf-8', timeout=60)
            return json.loads(output)

        assert run('self-test')['status'] == 'success'
        old = root / 'retired-api-skill'
        old.mkdir()
        (old / 'SKILL.md').write_text('external API image-only skill')
        rules = root / 'Agent.md'
        rules.write_text('Keep general rules.\nOld API constraint.\n')
        planfile = root / 'migration.json'
        run('migrate', 'scan', '--skills-root', str(root), '--rules', str(rules), '--output', str(root.parent / (root.name + '-plan.json')))
        external_plan = root.parent / (root.name + '-plan.json')
        try:
            plan = json.loads(external_plan.read_text())
        finally:
            external_plan.unlink()
        plan['reviewed'] = True
        for item in plan['inventory']:
            item.update(decision='remove', kind='external_image_api_only', reason='image-only test fixture')
        plan['edit_rules'][0].update(decision='edit', reason='old image-only constraint')
        selected = next(x for x in plan['inventory'] if Path(x['path']) == old)
        plan['remove_skills'] = [{**selected, 'kind': 'external_image_api_only', 'reason': 'test-only image API skill'}]
        plan['edit_rules'][0]['remove_text'] = ['Old API constraint.\r\n' if b'\r\n' in rules.read_bytes() else 'Old API constraint.\n']
        planfile.write_text(json.dumps(plan))
        receipt = run('migrate', 'apply', '--plan', str(planfile))
        assert not old.exists()
        assert rules.read_text() == 'Keep general rules.\n'
        assert run('install', '--migration-backup', receipt['backup'])['mode'] == 'portable'
        assert (state / 'install.json').is_file()
        assert run('update', '--auto')['status'] == 'portable_manual_update'
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            (state / 'config.json').write_text(json.dumps({'key_env': 'TEST_GATEWAY_KEY',
                'gateway_url': 'http://127.0.0.1:' + str(server.server_port)}), encoding='utf-8')
            assert 'default' in run('profiles')['profiles']
            image = root / 'input.png'
            image.write_bytes(raw.getvalue())
            for model in models:
                job = root / 'job.json'
                job.write_text(json.dumps({'profile': 'default', 'model': model, 'prompt': 'local test',
                                          'image': str(image), 'output_dir': str(root / 'outputs')}), encoding='utf-8')
                result = run('edit', '--job', str(job))
                assert result['status'] == 'success', result
                assert result['validation']['width'] == 4
                assert result['request_content_type'] == 'application/json'
                assert run('diagnose', '--task', result['task'])['request_content_type'] == 'application/json'
            assert posts == models
            run('migrate', 'restore', '--backup', receipt['backup'])
            assert old.exists()
            assert 'Old API constraint.' in rules.read_text()
        finally:
            server.shutdown()
            thread.join()
            server.server_close()
            shutil.rmtree(home)
    print(json.dumps({'status': 'success', 'python_git_on_path': False,
                      'isolated_install': True, 'loopback_edit_posts': len(posts),
                      'real_api_requests': 0, 'models': models}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('archive', type=Path)
    verify(p.parse_args().archive)

