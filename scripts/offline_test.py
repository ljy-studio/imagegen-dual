"""Offline regression checks: no credentials, network or paid calls."""
import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import client as c
import update as u
import installation_test as install


class Response:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self.headers = {}
        self.data = data

    def json(self):
        return self.data


class Tests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        state = patch.object(c, 'STATE', Path(temporary.name))
        state.start()
        self.addCleanup(state.stop)
        self.discovery = patch.object(c.accounts, 'discover', return_value=({}, []))
        self.discovery.start()
        self.addCleanup(self.discovery.stop)
    def test_error_details_and_edit(self):
        response = Response(400, {'error': {'message': 'invalid size fake-secret https://example.org/?token=abc', 'code': 'bad_size'}})
        response.headers = {'x-request-id': 'req-test'}
        details = c.error_detail(response, 'fake-secret')
        self.assertEqual(details['code'], 'bad_size')
        self.assertEqual(details['request_id'], 'req-test')
        self.assertNotIn('fake-secret', details['message'])
        self.assertNotIn('token=abc', details['message'])
        with tempfile.TemporaryDirectory() as temp, patch.object(c, 'session') as factory:
            image = Path(temp) / 'input.png'
            c.Image.new('RGB', (4, 4)).save(image)
            post = factory.return_value.__enter__.return_value.post
            post.return_value = response
            result = c.generate({'model': 'test', 'prompt': 'edit', 'image': str(image), 'output_dir': temp},
                                'fake-secret', [{'endpoint': c.DIRECT[0], 'models': ['test']}], 'edit')
            self.assertEqual(result['error']['code'], 'bad_size')
            self.assertTrue(post.call_args.args[0].endswith('/images/edits'))
            self.assertIn('files', post.call_args.kwargs)

    def test_installation_get_only(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(c, 'STATE', Path(temp)), patch.object(c, 'load', return_value=({'selected_profile': 'test'}, 'fake', c.DIRECT)), patch.object(install, 'probe', return_value={'status': 'success'}) as probe:
            report = install.run('test')
            self.assertEqual(probe.call_count, 10)
            self.assertEqual(report['generation_posts'], 0)

    def test_generate_fallback_and_unknown(self):
        raw = io.BytesIO()
        c.Image.new('RGB', (4, 4)).save(raw, format='PNG')
        response = Response(data={'data': [{'b64_json': base64.b64encode(raw.getvalue()).decode()}]})
        available = [{'endpoint': x, 'models': ['az/gpt-image-2.5-flare']} for x in c.DIRECT]
        with tempfile.TemporaryDirectory() as temp:
            job = {'prompt': 'offline', 'model': 'az/gpt-image-2.5-flare', 'output_dir': temp}
            with patch.object(c, 'session') as factory:
                post = factory.return_value.__enter__.return_value.post
                post.side_effect = [c.requests.ConnectTimeout(), response]
                r = c.generate(job, 'fake', available)
                self.assertEqual(r['status'], 'success')
                self.assertEqual(post.call_count, 2)
                self.assertEqual(r['validation']['width'], 4)
            for failure in [c.requests.ReadTimeout(), c.requests.ConnectionError(), Response(500), Response(429), Response(data={})]:
                with patch.object(c, 'session') as factory:
                    post = factory.return_value.__enter__.return_value.post
                    post.side_effect = [failure]
                    r = c.generate(job, 'fake', available)
                    self.assertNotEqual(r['status'], 'success')
                    self.assertEqual(post.call_count, 1)
            with patch.object(c, 'session') as factory:
                with self.assertRaises(ValueError):
                    c.generate(dict(job, model='removed'), 'fake', available)
                factory.assert_not_called()

    def test_route_switch(self):
        with patch.object(c, 'session') as factory:
            get = factory.return_value.__enter__.return_value.get
            get.side_effect = [c.requests.ConnectTimeout(), Response(data={'data': [{'id': 'new-model'}]})]
            result = c.routes('fake', c.DIRECT)
            self.assertEqual(result, [{'endpoint': c.DIRECT[1], 'models': ['new-model']}])

    def test_download_without_authorization(self):
        raw = io.BytesIO()
        c.Image.new('RGB', (4, 4)).save(raw, format='PNG')
        with tempfile.TemporaryDirectory() as temp, patch.object(c, 'session') as factory:
            get = factory.return_value.__enter__.return_value.get
            get.return_value.content = raw.getvalue()
            c.artifact(Path(temp), {'data': [{'url': 'https://example.org/image'}]})
            self.assertNotIn('headers', get.call_args.kwargs)
        with self.assertRaises(Exception):
            c.validate(raw.getvalue()[:20])

    def test_gateway_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / 'config.json').write_text(json.dumps({'key_env': 'TEST_ZIIKOO_KEY', 'gateway_url': 'http://127.0.0.1:1234'}))
            with patch.object(c, 'STATE', state), patch.dict(c.os.environ, {'TEST_ZIIKOO_KEY': 'fake'}):
                self.assertEqual(c.load('default')[2], ['http://127.0.0.1:1234/v1'])

    def test_explicit_selection_before_request(self):
        with patch.object(c, 'session') as factory:
            with self.assertRaises(c.SelectionRequired):
                c.generate({'prompt': 'offline'}, 'fake', [{'endpoint': c.DIRECT[0], 'models': ['gpt-image-2']}])
            factory.assert_not_called()
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / 'config.json').write_text(json.dumps({'profiles': {
                'HyperChain': {'key_env': 'TEST_H'},
                '智蔻信息': {'key_env': 'TEST_Z', 'gateway_url': 'http://127.0.0.1:1234/v1'}
            }}), encoding='utf-8')
            with patch.object(c, 'STATE', state), patch.dict(c.os.environ, {'TEST_H': 'h', 'TEST_Z': 'z'}):
                with self.assertRaises(c.SelectionRequired) as error:
                    c.load()
                self.assertEqual(set(error.exception.options), {'HyperChain', '智蔻信息'})
                self.assertEqual(c.load('智蔻信息')[1], 'z')
                self.assertEqual(c.load('HyperChain')[1], 'h')

    def test_update_preserves_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp)
            (state / 'update.json').write_text(json.dumps({'repository': 'https://example.org/skill.git'}))
            with patch.object(u, 'STATE', state), patch.object(u, 'git', side_effect=[str(u.ROOT), ' M SKILL.md']) as git:
                self.assertEqual(u.update()['status'], 'local_changes_preserved')
                self.assertEqual(git.call_count, 2)


if __name__ == '__main__':
    unittest.main()
