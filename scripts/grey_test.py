"""Grey-release regressions. Local mocks only; no image API calls."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import client as c
import install
import installation_test
import update


class Tests(unittest.TestCase):
    def setUp(self):
        receipt_dir = tempfile.TemporaryDirectory()
        self.addCleanup(receipt_dir.cleanup)
        (Path(receipt_dir.name) / "manifest.json").write_text(json.dumps({"skills_roots": [], "inventory_review": [], "skills": [], "rule_files": [], "rules": []}))
        mock = patch.object(install, "verify_migration", return_value=receipt_dir.name)
        mock.start()
        self.addCleanup(mock.stop)
        state_dir = tempfile.TemporaryDirectory()
        self.addCleanup(state_dir.cleanup)
        state = patch.object(c, "STATE", Path(state_dir.name))
        state.start()
        self.addCleanup(state.stop)

    def edit_job(self, temp, model, **extra):
        image = Path(temp) / "input.png"
        c.Image.new("RGB", (4, 4)).save(image)
        return dict({"model": model, "prompt": "edit", "image": str(image), "output_dir": temp}, **extra)

    def test_known_failing_edit_model_is_blocked_before_post(self):
        model = "gpt-image-2.5-sunburst"
        routes = [{"endpoint": c.DIRECT[0], "models": [model, "az/gpt-image-2.5-sunburst"]}]
        with tempfile.TemporaryDirectory() as temp, patch.object(c, "session") as factory:
            with self.assertRaises(c.EditUnsupported) as error:
                c.generate(self.edit_job(temp, model), "fake", routes, "edit")
            factory.assert_not_called()
            self.assertEqual(error.exception.detail["posts_sent"], 0)
            self.assertEqual(error.exception.detail["edit"], "failing")
            self.assertIn("az/gpt-image-2.5-sunburst", error.exception.detail["edit_unverified_models"])

    def test_generate_is_not_blocked_for_edit_failing_model(self):
        model = "gpt-image-2.5-sunburst"
        with tempfile.TemporaryDirectory() as temp, patch.object(c, "session") as factory:
            post = factory.return_value.__enter__.return_value.post
            post.return_value.status_code = 400
            post.return_value.headers = {}
            post.return_value.json.return_value = {"error": {"message": "bad"}}
            c.generate({"model": model, "prompt": "p", "output_dir": temp}, "fake", [{"endpoint": c.DIRECT[0], "models": [model]}])
            self.assertEqual(post.call_count, 1)

    def test_force_and_profile_override_allow_one_post(self):
        model = "gpt-image-2.5-sunburst"
        routes = [{"endpoint": c.DIRECT[0], "models": [model]}]
        for job_extra, overrides in (({"force_edit": True}, None), ({}, {model: True})):
            with tempfile.TemporaryDirectory() as temp, patch.object(c, "session") as factory:
                post = factory.return_value.__enter__.return_value.post
                post.return_value.status_code = 400
                post.return_value.headers = {}
                post.return_value.json.return_value = {"error": {"message": "bad"}}
                c.generate(self.edit_job(temp, model, **job_extra), "fake", routes, "edit", overrides)
                self.assertEqual(post.call_count, 1)

    def test_unsupported_response_is_remembered(self):
        routes = [{"endpoint": c.DIRECT[0], "models": ["gpt-image-2"]}]
        with tempfile.TemporaryDirectory() as temp, patch.object(c, "session") as factory:
            post = factory.return_value.__enter__.return_value.post
            post.return_value.status_code = 400
            post.return_value.headers = {"x-request-id": "req-1"}
            post.return_value.json.return_value = {"error": {"message": "This model does not support image edits"}}
            first = c.generate(self.edit_job(temp, "gpt-image-2"), "fake", routes, "edit")
            self.assertEqual(first["edit_support"], "unsupported")
            with self.assertRaises(c.EditUnsupported):
                c.generate(self.edit_job(temp, "gpt-image-2"), "fake", routes, "edit")
            self.assertEqual(post.call_count, 1)

    def test_single_500_does_not_block_but_repeat_does(self):
        routes = [{"endpoint": c.DIRECT[0], "models": ["gpt-image-2"]}]
        with tempfile.TemporaryDirectory() as temp, patch.object(c, "session") as factory:
            post = factory.return_value.__enter__.return_value.post
            post.return_value.status_code = 500
            post.return_value.headers = {}
            post.return_value.json.return_value = {"error": {"message": "Service temporarily unavailable"}}
            c.generate(self.edit_job(temp, "gpt-image-2"), "fake", routes, "edit")
            c.generate(self.edit_job(temp, "gpt-image-2"), "fake", routes, "edit")
            with self.assertRaises(c.EditUnsupported):
                c.generate(self.edit_job(temp, "gpt-image-2"), "fake", routes, "edit")
            self.assertEqual(post.call_count, 2)

    def test_catalog_does_not_apply_to_custom_gateway(self):
        model = "gpt-image-2.5-sunburst"
        self.assertEqual(c.edit_support(model, "http://127.0.0.1:9000/v1")[0], "unknown")
        self.assertEqual(c.edit_support(model, c.DIRECT[0], {model: False})[0], "unsupported")

    def test_offline_update_backs_off(self):
        calls = [str(update.ROOT), "", "https://github.com/ljy-studio/imagegen-dual.git", "old", OSError("offline")]
        with tempfile.TemporaryDirectory() as temp, patch.object(update, "STATE", Path(temp)), patch.object(update, "git", side_effect=calls) as git:
            self.assertEqual(update.update(auto=True)["status"], "offline_current_version_preserved")
            self.assertEqual(update.update(auto=True)["status"], "checked_recently")
            self.assertEqual(git.call_count, 5)

    def test_global_pip_is_not_used(self):
        with patch.object(install.sys, "prefix", install.sys.base_prefix), patch.object(install, "run") as run:
            with self.assertRaisesRegex(ValueError, "private_venv"):
                install.initialize(archive=True)
            run.assert_not_called()

    def test_archive_install_without_git(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(install, 'STATE', Path(temp)), patch.object(install, 'run'), patch.object(install.subprocess, 'check_output', side_effect=FileNotFoundError):
            result = install.initialize(skip_deps=True, archive=True)
            self.assertEqual(result['mode'], 'archive')
            self.assertIsNone(result['commit'])

    def test_json_edit_and_no_protocol_retry(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(c, 'session') as factory:
            image = Path(temp) / 'input.png'
            c.Image.new('RGB', (4, 4)).save(image)
            post = factory.return_value.__enter__.return_value.post
            post.return_value.status_code = 400
            post.return_value.headers = {}
            post.return_value.json.return_value = {'error': {'message': "invalid character '-' in numeric literal"}}
            result = c.generate({'model': 'test', 'prompt': 'edit', 'image': str(image), 'edit_transport': 'json', 'output_dir': temp}, 'fake', [{'endpoint': c.DIRECT[0], 'models': ['test']}], 'edit')
            self.assertEqual(post.call_count, 1)
            self.assertIn('json', post.call_args.kwargs)
            self.assertNotIn('files', post.call_args.kwargs)
            encoded = post.call_args.kwargs['json']['images'][0]['image_url']
            self.assertEqual(base64.b64decode(encoded.split(',', 1)[1]), image.read_bytes())
            self.assertEqual(result['request_content_type'], 'application/json')
            self.assertEqual(result['status'], 'rejected')

    def test_invalid_transport_prevents_post(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(c, 'session') as factory:
            image = Path(temp) / 'input.png'
            c.Image.new('RGB', (4, 4)).save(image)
            with self.assertRaisesRegex(ValueError, 'edit_transport'):
                c.generate({'model': 'test', 'prompt': 'edit', 'image': str(image), 'edit_transport': 'guess', 'output_dir': temp}, 'fake', [{'endpoint': c.DIRECT[0], 'models': ['test']}], 'edit')
            factory.assert_not_called()

    def test_minimal_initialization(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(c, 'STATE', Path(temp)), patch.object(c, 'load', return_value=({'selected_profile': 'test'}, 'fake', c.DIRECT)), patch.object(installation_test, 'probe', return_value={'status': 'success'}) as probe:
            report = installation_test.run('test')
            self.assertEqual(probe.call_count, 2)
            self.assertEqual(report['generation_posts'], 0)


if __name__ == '__main__':
    unittest.main()
