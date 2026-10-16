"""Permission migration must reject unsafe roots without mutating them."""
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
from unittest.mock import patch

from overmind.store import Store
from overmind.data import benchmark
from overmind.lab import DEFAULTS


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)

    def snapshot(self,root):
        result={}
        for path in [root,*root.rglob('*')]:
            info=path.lstat()
            result[str(path.relative_to(root))]=(stat.S_IMODE(info.st_mode),
                os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None)
        return result

    def unchanged_rejection(self,root):
        before=self.snapshot(root)
        with self.assertRaises(ValueError):Store(root)
        self.assertEqual(self.snapshot(root),before)

    def test_unrelated_directory_even_named_lab_data_is_untouched(self):
        root=self.base/'lab-data';root.mkdir(mode=0o755)
        (root/'important').mkdir();(root/'important'/'program').write_text('unrelated')
        (root/'important'/'program').chmod(0o755)
        self.unchanged_rejection(root)

    def test_ignore_file_alone_does_not_prove_ownership(self):
        root=self.base/'data';root.mkdir()
        (root/'.gitignore').write_text('# OVERMIND private laboratory data\n*\n')
        self.unchanged_rejection(root)

    def test_home_empty_or_not_is_rejected(self):
        root=self.base/'home';root.mkdir()
        with patch('overmind.store.Path.home',return_value=root):self.unchanged_rejection(root)

    def test_source_and_filesystem_roots_are_rejected(self):
        for root in (Path('/'),Path(__file__).resolve().parents[1]):
            with self.subTest(root=str(root)),self.assertRaises(ValueError):Store(root)

    def test_symlink_root_and_parent_are_untouched(self):
        target=self.base/'real';Store(target)
        link=self.base/'link';link.symlink_to(target,target_is_directory=True)
        before=self.snapshot(target)
        for root in (link,link/'new'):
            with self.assertRaises(ValueError):Store(root)
        self.assertEqual(self.snapshot(target),before)

    def test_complete_preflight_before_any_chmod_or_marker_write(self):
        store=Store(self.base/'data');rid=store.create(DEFAULTS,benchmark())
        # Represent a pre-marker installation with old, public permissions.
        (store.root/'.overmind-lab').unlink();store.root.chmod(0o755)
        store.artifact(rid,'first.json',{'value':'preserve'})
        (store.root/rid/'first.json').chmod(0o644)
        outside=self.base/'outside';outside.write_text('private unrelated');outside.chmod(0o640)
        (store.root/rid/'last.json').symlink_to(outside)
        self.unchanged_rejection(store.root)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode),0o640)

    def test_hardlink_cannot_change_an_external_inode(self):
        store=Store(self.base/'data');rid=store.create(DEFAULTS,benchmark())
        outside=self.base/'outside';outside.write_text('unchanged');outside.chmod(0o644)
        os.link(outside,store.root/rid/'linked.json')
        self.unchanged_rejection(store.root)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode),0o644)

    def test_special_file_rejected_without_any_changes(self):
        store=Store(self.base/'data');rid=store.create(DEFAULTS,benchmark())
        os.mkfifo(store.root/rid/'pipe')
        # Snapshot skips reading the FIFO, which would block.
        before=stat.S_IMODE(store.root.stat().st_mode)
        with self.assertRaises(ValueError):Store(store.root)
        self.assertTrue(stat.S_ISFIFO((store.root/rid/'pipe').lstat().st_mode))
        self.assertEqual(stat.S_IMODE(store.root.stat().st_mode),before)

    def test_unrelated_entries_rejected_even_with_valid_database(self):
        for name,directory in [('photos',True),('other.txt',False)]:
            with self.subTest(name=name):
                store=Store(self.base/name.replace('.','-'))
                path=store.root/name
                if directory:path.mkdir()
                else:path.write_text('unrelated')
                self.unchanged_rejection(store.root)

    def test_invalid_database_and_marker_rejected_without_changes(self):
        for invalid in ('database','marker'):
            root=self.base/invalid;root.mkdir()
            if invalid=='database':
                with sqlite3.connect(root/'lab.sqlite3') as db:db.execute('CREATE TABLE unrelated(value)')
            else:(root/'.overmind-lab').write_text('not an ownership marker')
            self.unchanged_rejection(root)

    def test_new_and_empty_roots_get_private_ownership_marker(self):
        for name in ('new','empty'):
            root=self.base/name
            if name=='empty':root.mkdir(mode=0o755)
            Store(root);Store(root)
            self.assertEqual((root/'.overmind-lab').read_text(),'OVERMIND laboratory v1\n')
            for path in [root,*root.rglob('*')]:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o700 if path.is_dir() else 0o600)

    def test_recognized_legacy_migration_preserves_evidence(self):
        store=Store(self.base/'legacy');rid=store.create(DEFAULTS,benchmark())
        store.artifact(rid,'baseline.json',{'accuracy':.825})
        (store.root/'.overmind-lab').unlink()
        before=self.snapshot(store.root)
        store.root.chmod(0o755)
        for path in store.root.rglob('*'):path.chmod(0o755 if path.is_dir() else 0o644)
        reopened=Store(store.root)
        self.assertEqual(reopened.get(rid)['status'],'ready')
        after=self.snapshot(store.root)
        self.assertEqual({k:v[1] for k,v in before.items()},
                         {k:v[1] for k,v in after.items() if k!='.overmind-lab'})
        for path in [store.root,*store.root.rglob('*')]:
            self.assertEqual(stat.S_IMODE(path.stat().st_mode),0o700 if path.is_dir() else 0o600)
