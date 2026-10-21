import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from overmind.bundle import export_bundle, validate_bundle

class RecordedStore:
    def get(self,rid):return {'status':'completed','config':{'student':{'kind':'linear'}}}
    def read(self,rid,name):
        if name in ('baseline-test.json','candidate-test.json'):
            return {'accuracy':1,'count':1,'results':[{'input':'PRIVATE DATASET TEXT','target':'yes','prediction':'yes','correct':True}]}
        if name=='report.json':return {'candidate_sha256':'fixture metadata only'}
        raise FileNotFoundError(name)

class BundleTests(unittest.TestCase):
    def test_export_is_private_minimized_and_checksum_validated(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'evidence.zip'
            export_bundle(RecordedStore(),'fixture',path)
            result=validate_bundle(path)
            self.assertFalse(result['includes_dataset'])
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with zipfile.ZipFile(path) as archive:
                self.assertNotIn(b'PRIVATE DATASET TEXT',archive.read('candidate-test.json'))
            with self.assertRaises(FileExistsError):export_bundle(RecordedStore(),'fixture',path)
            with zipfile.ZipFile(path,'a') as archive:archive.writestr('../escape.json','{}')
            with self.assertRaisesRegex(ValueError,'Unsafe'):validate_bundle(path)
            self.assertFalse((Path(root).parent/'escape.json').exists())

    def test_modified_content_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'bad.zip'
            manifest={'format':'gafaw.evidence.v1','files':{'report.json':hashlib.sha256(b'{}').hexdigest()}}
            with zipfile.ZipFile(path,'w') as archive:
                archive.writestr('manifest.json',json.dumps(manifest));archive.writestr('report.json','{"modified":true}')
            with self.assertRaisesRegex(ValueError,'checksum'):validate_bundle(path)
