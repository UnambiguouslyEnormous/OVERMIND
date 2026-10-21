import copy
import json
from pathlib import Path
import tempfile
import unittest
from overmind.data import benchmark, digest
from overmind.workshop import prepare, import_file, export_version, rows_from_text, editable_jsonl
from overmind.inventory import inspect_local


def records():
    return [{'input':f'{label} sample {i}', 'target':label} for label in ('one','two') for i in range(40)]

class WorkshopTests(unittest.TestCase):
    def test_reproducible_split_deduplicates_before_assignment(self):
        rows=records();a=prepare(rows+rows[:2],'CC0-1.0',seed=7)
        b=prepare(list(reversed(rows))+rows[:2],'CC0-1.0',seed=7)
        self.assertEqual(a,b)
        self.assertEqual(a['provenance']['duplicates_removed'],2)
        self.assertNotEqual(a['train'],prepare(rows,'CC0-1.0',seed=8)['train'])
        sets=[{r['input'] for r in a[s]} for s in ('train','validation','test')]
        self.assertFalse(sets[0]&sets[1] or sets[1]&sets[2] or sets[0]&sets[2])
        self.assertEqual(len(set.union(*sets)),80)

    def test_conflicting_duplicates_and_explicit_leakage_rejected(self):
        rows=records()
        rows.append({'input':'  ONE SAMPLE 0 ', 'target':'two'})
        with self.assertRaisesRegex(ValueError,'conflicting'):prepare(rows,'CC0')
        data=benchmark();rows=rows_from_text(editable_jsonl(data),'jsonl')
        rows.append({**rows[0],'split':'test'})
        with self.assertRaisesRegex(ValueError,'leakage'):prepare(rows,'CC0')

    def test_edit_preserves_explicit_splits(self):
        data=benchmark()
        result=prepare(rows_from_text(editable_jsonl(data),'jsonl'),'CC0-1.0')
        for split in ('train','validation','test'):self.assertEqual(data[split],result[split])
        self.assertEqual(result['provenance']['split_policy'],'preserved')

    def test_private_immutable_export_and_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'version.json';data=prepare(records(),'CC0-1.0')
            export_version(data,path)
            self.assertEqual(digest(data),digest(import_file(path,'')))
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):export_version(data,path)
            link=Path(root)/'link.json';link.symlink_to(path)
            with self.assertRaises(FileExistsError):export_version(data,link)

    def test_csv_and_jsonl_import_with_license_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'source.csv'
            path.write_text('input,target\n'+'\n'.join(f'{r["input"]},{r["target"]}' for r in records()))
            data=import_file(path,'CC0-1.0')
            self.assertEqual(len(data['provenance']['source_sha256']),64)
            with self.assertRaisesRegex(ValueError,'license'):import_file(path,'')
            with self.assertRaisesRegex(ValueError,'input'):rows_from_text('text,label\nhello,one','csv')

class InventoryTests(unittest.TestCase):
    def test_metadata_never_executes_custom_model_code(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)
            (path/'config.json').write_text(json.dumps({'model_type':'fixture','auto_map':{'AutoModel':'evil.Model'}}))
            (path/'model.py').write_text('raise RuntimeError("MUST NEVER EXECUTE")')
            (path/'model.safetensors').write_bytes(b'fixture metadata only; not valid weights')
            (path/'tokenizer.json').write_text('{}')
            result=inspect_local(path)
            self.assertTrue(result['custom_code_declared'])
            self.assertIn('unverified',result['training_status'])
            self.assertIn('Unknown',result['license_status'])
            (path/'config.json').unlink();(path/'config.json').symlink_to(path/'tokenizer.json')
            with self.assertRaisesRegex(ValueError,'symlink'):inspect_local(path)
