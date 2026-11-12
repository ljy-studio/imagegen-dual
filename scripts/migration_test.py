"""Verify reversible cleanup preserves unrelated skills and exact rule bytes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import migrate as m
import install


class Tests(unittest.TestCase):
    def test_blank_cleanup_cannot_skip_existing_skills(self):
        plan = m.inventory([self.skills], [self.rules])
        plan["reviewed"] = True
        with self.assertRaisesRegex(ValueError, "unreviewed_skill"):
            m.apply(plan, self.state)
        self.assertTrue(self.old.exists())

    def test_omitted_inventory_entry_is_rejected(self):
        plan = m.inventory([self.skills], [self.rules])
        plan["reviewed"] = True
        plan["inventory"] = []
        with self.assertRaisesRegex(ValueError, "inventory_scope_changed"):
            m.apply(plan, self.state)

    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.base = Path(t.name).resolve()
        self.skills = self.base / 'skills'
        self.skills.mkdir()
        self.old = self.skills / 'imagegen-dual'
        self.old.mkdir()
        (self.old / 'SKILL.md').write_text('old image API', encoding='utf-8')
        (self.old / 'custom.txt').write_text('preserve me')
        self.other = self.skills / 'designer'
        self.other.mkdir()
        (self.other / 'SKILL.md').write_text('web and illustration design')
        self.rules = self.base / 'AGENTS.md'
        self.block = '## Old image API\r\nUse the retired imagegen-dual.\r\n\r\n'
        self.before = ('\ufeff# Project\r\nKeep general rules.\r\n\r\n' + self.block + '## Research\r\nPreserve this.\r\n').encode('utf-8')
        self.rules.write_bytes(self.before)
        self.plan = m.inventory([self.skills], [self.rules])
        self.plan['reviewed'] = True
        for item in self.plan['inventory']:
            item.update(decision='remove' if Path(item['path']) == self.old else 'keep', kind='old_imagegen_dual' if Path(item['path']) == self.old else 'unrelated', reason='reviewed test fixture purpose')
        found = next(x for x in self.plan['inventory'] if Path(x['path']) == self.old)
        self.plan['remove_skills'] = [{**found, 'kind': 'old_imagegen_dual', 'reason': 'old version inspected'}]
        self.plan['edit_rules'][0]['remove_text'] = [self.block]
        self.plan['edit_rules'][0].update(decision='edit', reason='retired API-specific rule')
        self.state = self.base / 'state'

    def test_cleanup_and_restore(self):
        result = m.apply(self.plan, self.state)
        self.assertFalse(self.old.exists())
        self.assertTrue(self.other.exists())
        self.assertEqual(self.rules.read_bytes(), self.before.replace(self.block.encode(), b''))
        m.restore(result['backup'])
        self.assertEqual(self.rules.read_bytes(), self.before)
        self.assertEqual((self.old / 'custom.txt').read_text(), 'preserve me')

    def test_changed_rule_blocks_all_mutations(self):
        self.rules.write_bytes(self.before + b'new')
        with self.assertRaisesRegex(ValueError, 'changed_since_review'):
            m.apply(self.plan, self.state)
        self.assertTrue(self.old.exists())

    def test_outside_scope_rejected(self):
        self.plan['skills_roots'] = [str(self.base / 'other')]
        with self.assertRaises(ValueError):
            m.apply(self.plan, self.state)
        self.assertTrue(self.old.exists())

    def test_changed_skill_preserved(self):
        (self.old / 'new.txt').write_text('new')
        with self.assertRaisesRegex(ValueError, 'changed_since_review'):
            m.apply(self.plan, self.state)
        self.assertTrue(self.old.exists())

    def test_restore_preserves_new_user_edits(self):
        result = m.apply(self.plan, self.state)
        self.rules.write_bytes(b'new user rules')
        with self.assertRaisesRegex(ValueError, 'modified_after'):
            m.restore(result['backup'])
        self.assertEqual(self.rules.read_bytes(), b'new user rules')

    def test_backup_not_discoverable_as_skill(self):
        with self.assertRaisesRegex(ValueError, 'outside_skill'):
            m.apply(self.plan, self.skills / 'backup')
        self.assertTrue(self.old.exists())

    def test_fresh_install_requires_receipt(self):
        with self.assertRaisesRegex(ValueError, 'migration_required'):
            install.verify_migration(None)

    def test_reviewed_empty_inventory_is_valid(self):
        empty = self.base / 'empty-skills'
        empty.mkdir()
        plan = m.inventory([empty], [])
        plan['reviewed'] = True
        result = m.apply(plan, self.state)
        with patch.object(install, 'ROOT', empty / 'imagegen-dual'):
            self.assertEqual(install.verify_migration(result['backup']), result['backup'])

    def test_failure_restores_already_moved_skill(self):
        original = m.write_bytes
        def fail_rule(path, raw):
            if path == self.rules:
                raise OSError("simulated_write_failure")
            return original(path, raw)
        with patch.object(m, "write_bytes", side_effect=fail_rule):
            with self.assertRaises(OSError):
                m.apply(self.plan, self.state)
        self.assertTrue(self.old.exists())
        self.assertEqual(self.rules.read_bytes(), self.before)

    def test_name_is_enforced_before_install(self):
        with patch.object(install, "ROOT", self.base / "renamed-copy"):
            with self.assertRaisesRegex(ValueError, "directory_must_be"):
                install.initialize(skip_deps=True, archive=True)


if __name__ == '__main__':
    unittest.main()

