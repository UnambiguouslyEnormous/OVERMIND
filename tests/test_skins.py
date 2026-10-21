"""Focused skin trust-boundary tests; real GTK switching lives in desktop_smoke.py."""
from contextlib import closing
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from overmind.skins import SkinLibrary, PreparedSkin, export_package, load_package, load_builtin, validate

class SkinTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.library=SkinLibrary(self.root/'library')

    def package(self,entries):
        path=self.root/'test.gafawskin'
        with zipfile.ZipFile(path,'w') as archive:
            for name,raw in entries:archive.writestr(name,raw)
        return path

    def test_multiple_skins_roundtrip_and_saved_selection(self):
        skins,errors=self.library.list()
        self.assertEqual([s.id for s in skins],['black-titanium','phosphor-night'])
        self.assertEqual(errors,[]);self.assertEqual(self.library.selected(),'black-titanium')
        skin=load_builtin('black-titanium');skin.manifest['id']='community-metal'
        package=self.root/'community.gafawskin';export_package(skin,package)
        installed=self.library.install(package)
        self.assertEqual(installed.manifest,skin.manifest);self.assertEqual(installed.assets,skin.assets)
        self.library.select(installed.id)
        self.assertEqual(SkinLibrary(self.library.root).selected(),installed.id)
        with closing(PreparedSkin(installed)) as prepared:
            self.assertIn(b'file://',prepared.css)
            self.assertIn(b'outline:2px solid',prepared.css)
        with self.assertRaises(FileExistsError):self.library.install(package)
        self.assertEqual(package.stat().st_mode & 0o777,0o600)

    def test_rejects_paths_links_duplicates_and_oversized_expansion(self):
        manifest=json.dumps(load_builtin('phosphor-night').manifest)
        for name in ('../outside.svg','/absolute.svg','assets/../../outside.svg','assets\\escape.svg'):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):load_package(self.package([('manifest.json',manifest),(name,'{}')]))
        link=zipfile.ZipInfo('assets/link.svg');link.create_system=3;link.external_attr=0o120777<<16
        with self.assertRaisesRegex(ValueError,'links'):load_package(self.package([('manifest.json',manifest),(link,'outside')]))
        with self.assertWarns(UserWarning):path=self.package([('manifest.json',manifest),('manifest.json',manifest)])
        with self.assertRaisesRegex(ValueError,'Duplicate'):load_package(path)
        path=self.package([('manifest.json',manifest),('assets/huge.svg','x'*2_000_001)])
        with self.assertRaisesRegex(ValueError,'limit'):load_package(path)
        self.assertFalse((self.root/'outside.svg').exists())

    def test_rejects_executable_css_external_svg_and_font_payloads(self):
        manifest=load_builtin('phosphor-night').manifest
        for extra in ({'css':'@import url(https://example.invalid)'},{'script':'evil.py'},{'font':{'family':'x"; opacity:0;'}}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):validate({**manifest,**extra},{})
        for payload in (b'<svg width="10" height="10"><script>alert(1)</script></svg>',
                        b'<svg width="10" height="10"><image href="file:///etc/passwd"/></svg>',
                        b'<?xml-stylesheet href="https://example.invalid/a.css"?><svg width="10" height="10"/>',
                        b'<!DOCTYPE svg [<!ENTITY x SYSTEM "file:///etc/passwd">]><svg width="10" height="10"/>'):
            with self.subTest(payload=payload),self.assertRaises(ValueError):validate(manifest,{'assets/evil.svg':payload})
        with self.assertRaisesRegex(ValueError,'Only static'):validate(manifest,{'assets/evil.py':b'raise RuntimeError()'})
        with self.assertRaisesRegex(ValueError,'Unknown surface'):validate({**manifest,'surfaces':{'button':{'opacity':0}}},{})

    def test_invalid_installed_skin_is_reported_and_safe_skin_available(self):
        self.library.select('phosphor-night')
        (self.library.root/'broken.gafawskin').write_bytes(b'not a zip')
        skins,errors=self.library.list()
        self.assertEqual(len(skins),2);self.assertEqual(len(errors),1)
        self.assertEqual(self.library.selected(),'phosphor-night')
        (self.library.root/'selection.json').write_text('{"skin":"missing"}')
        with self.assertRaises(OSError):self.library.selected()
        self.assertEqual(self.library.get('black-titanium').id,'black-titanium')

    def test_reserved_ids_and_library_links_are_rejected(self):
        path=self.root/'builtin.gafawskin';export_package(load_builtin('black-titanium'),path)
        with self.assertRaisesRegex(ValueError,'reserved'):self.library.install(path)
        actual=self.root/'actual';actual.mkdir();self.library.root.symlink_to(actual)
        with self.assertRaisesRegex(ValueError,'symlinks'):self.library.list()
