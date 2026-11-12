"""Local Git and provider integration checks. No API calls."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import update as u
import accounts
import json
import sqlite3
import migrate


class Tests(unittest.TestCase):
    def test_readonly_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            directory = home / '.cc-switch'
            directory.mkdir()
            db = directory / 'cc-switch.db'
            conn = sqlite3.connect(db)
            conn.execute('create table providers (id text,app_type text,name text,settings_config text)')
            conf = '[model_providers.x]' + chr(10) + 'base_url="https://api.gaoxin.net.cn/v1"'
            conn.execute('insert into providers values (?,?,?,?)', ('a','codex','same',json.dumps({'config':conf, 'auth':{'OPENAI_API_KEY':'test-one'}})))
            conn.commit(); conn.close()
            directory = home / '.config/magpie'
            directory.mkdir(parents=True)
            p = directory / 'providers.json'
            p.write_text(json.dumps({'providers':[{'id':'b','name':'same','baseAPI':'https://api-sh.gaoxin.net.cn','key':'test-two'}]}))
            before = (db.read_bytes(), p.read_bytes())
            found, notices = accounts.discover(home)
            self.assertEqual(len(found), 2)
            self.assertNotIn('test-one', json.dumps(found))
            self.assertNotIn('test-two', json.dumps(found))
            self.assertEqual(accounts.discover(home, 'magpie:b')[0]['magpie:b']['key'], 'test-two')
            self.assertEqual(before, (db.read_bytes(), p.read_bytes()))

    def test_magpie_indirection_schema(self):
        # Real magpie records name the URL field via baseAPI instead of holding the URL directly.
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            directory = home / '.config/magpie'
            directory.mkdir(parents=True)
            record = {'id': 'api-sh-gaoxin-net', 'name': 'imagegen-test', 'key': 'data-key',
                      'baseAPI': 'responses', 'responses': 'https://api.gaoxin.net.cn/v1'}
            (directory / 'providers.json').write_text(json.dumps({'providers': [record]}))
            found, notices = accounts.discover(home)
            self.assertIn('magpie:api-sh-gaoxin-net', found)
            self.assertEqual(found['magpie:api-sh-gaoxin-net']['label'], 'imagegen-test')
            self.assertNotIn('data-key', json.dumps(found))
            selected, _ = accounts.discover(home, 'magpie:api-sh-gaoxin-net')
            self.assertEqual(selected['magpie:api-sh-gaoxin-net']['key'], 'data-key')

    def test_update_real_git(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = base/'source'; installed = base/'skills/imagegen-dual'; state = base/'state'
            installed.parent.mkdir()
            shutil.copytree(u.ROOT, source, ignore=shutil.ignore_patterns('__pycache__', '.git', '.venv', '.build-venv', 'build', 'dist'))
            def git(*args, cwd=source):
                return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
            git('init', '-b', 'main'); git('config','user.email','test@example.invalid'); git('config','user.name','Offline test')
            git('add','.'); git('commit','-m','initial')
            git('clone', str(source), str(installed), cwd=base)
            trusted = 'https://github.com/ljy-studio/imagegen-dual.git'
            git('remote','set-url','origin', trusted,cwd=installed)
            git('config', 'url.'+str(source)+'.insteadOf',trusted,cwd=installed)
            spec=importlib.util.spec_from_file_location('candidate_updater',installed/'scripts/update.py')
            updater=importlib.util.module_from_spec(spec); spec.loader.exec_module(updater)
            updater.STATE=state
            (source/'version.json').write_text('{"version":"0.1.1","config_schema":1}')
            git('add','.');git('commit','-m','valid update')
            self.assertEqual(updater.update()['status'],'updated')
            self.assertEqual(updater.update()['status'],'up_to_date')
            (installed/'SKILL.md').write_text('local edit')
            self.assertEqual(updater.update()['status'],'local_changes_preserved')
            git('checkout','--','SKILL.md',cwd=installed)
            (source/'requirements.txt').write_text('changed-dependency')
            git('add','.');git('commit','-m','dependency change')
            self.assertEqual(updater.update()['status'],'dependency_change_requires_manual_upgrade')

    def test_install(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); source = base/'source'; installed = base/'skills/imagegen-dual'; state = base/'state'
            installed.parent.mkdir()
            shutil.copytree(u.ROOT, source, ignore=shutil.ignore_patterns('__pycache__', '.git', '.venv', '.build-venv', 'build', 'dist'))
            def git(*args, cwd=source):
                return subprocess.check_output(['git', *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True).strip()
            git('init','-b','main'); git('config','user.email','test@example.invalid'); git('config','user.name','Offline test')
            git('add','.'); git('commit','-m','install test')
            trusted = 'https://github.com/ljy-studio/imagegen-dual.git'
            git('clone',str(source),str(installed),cwd=base)
            git('remote','set-url','origin',trusted,cwd=installed)
            spec=importlib.util.spec_from_file_location('candidate_install',installed/'scripts/install.py')
            installer=importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
            installer.STATE=state
            plan=migrate.inventory([installed.parent], [])
            plan['reviewed']=True
            receipt=migrate.apply(plan, state)
            result=installer.initialize(skip_deps=True, migration_backup=receipt['backup'])
            self.assertEqual(result['repository'],trusted)
            self.assertTrue((state/'install.json').is_file())


if __name__=='__main__':
    unittest.main()
