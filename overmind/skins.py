"""Declarative skin packages. No imported CSS, scripts, fonts, or external resources."""
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tempfile
import xml.etree.ElementTree as ET
import zipfile

BUILTINS = Path(__file__).with_name('skins')
FORMAT = 'gafaw.skin.v1'
MAX_TOTAL = 8_000_000
MAX_ASSET = 2_000_000
SELECTORS = {
    'header':'headerbar', 'sidebar':'.sidebar', 'panel':'.card', 'metric':'.metric',
    'button':'button', 'button_hover':'button:hover', 'button_active':'button:active, button:checked',
    'button_disabled':'button:disabled, button.primary:disabled, button.danger:disabled', 'button_primary':'button.primary', 'button_danger':'button.danger',
    'input':'entry, spinbutton, textview, textview text, combobox button', 'notebook':'notebook header',
    'tab':'notebook tab', 'tab_active':'notebook tab:checked', 'list_selected':'list row:selected',
    'progress_trough':'progressbar trough', 'progress':'progressbar progress', 'selection':'selection',
}
PALETTE = {'background','text','muted','accent','focus'}
COLOR = re.compile(r'#[0-9a-fA-F]{6}\Z')
IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,47}\Z')


def _path(name):
    if (not isinstance(name,str) or not name or '\\' in name or '\x00' in name
            or PurePosixPath(name).is_absolute() or any(p in ('','.','..') for p in name.split('/'))):
        raise ValueError('Unsafe skin package path.')
    return name


def _color(value,colors):
    value=colors.get(value,value) if isinstance(value,str) else value
    if not isinstance(value,str) or not COLOR.fullmatch(value):raise ValueError('Colors must be #RRGGBB or a defined palette name.')
    return value


def _asset(name,raw):
    _path(name)
    if not name.startswith('assets/') or len(raw)>MAX_ASSET:raise ValueError('Assets must be bounded files under assets/.')
    if name.endswith('.png'):
        if len(raw)<33 or raw[:8]!=b'\x89PNG\r\n\x1a\n' or raw[12:16]!=b'IHDR':raise ValueError('Invalid PNG header.')
        w,h=struct.unpack('>II',raw[16:24])
        if not 0<w<=4096 or not 0<h<=4096:raise ValueError('PNG dimensions exceed 4096 pixels.')
    elif name.endswith('.svg'):
        if b'<?' in raw or re.search(br'<!\s*(DOCTYPE|ENTITY)',raw,re.I):raise ValueError('SVG processing instructions, entities and document types are forbidden.')
        try:root=ET.fromstring(raw)
        except ET.ParseError as error:raise ValueError('Invalid SVG.') from error
        tags={'svg','defs','linearGradient','radialGradient','stop','path','rect','circle','ellipse','line','polyline','polygon','g'}
        attrs={'width','height','viewBox','id','x','y','x1','x2','y1','y2','cx','cy','r','rx','ry','d','points','fill','stroke','stroke-width','stroke-opacity','fill-opacity','opacity','offset','stop-color','stop-opacity','transform','gradientUnits'}
        nodes=list(root.iter())
        if len(nodes)>10000 or root.tag not in ('svg','{http://www.w3.org/2000/svg}svg'):raise ValueError('Invalid SVG root or too many shapes.')
        for node in nodes:
            if node.tag not in tags and node.tag not in {'{http://www.w3.org/2000/svg}'+tag for tag in tags}:raise ValueError('Unsupported SVG element; only static shapes are allowed.')
            for attr,value in node.attrib.items():
                if attr not in attrs or len(value)>65536:raise ValueError('Unsupported SVG attribute.')
                if 'url' in value.lower() and (attr not in ('fill','stroke') or not re.fullmatch(r'url\(#[A-Za-z_][A-Za-z0-9_-]*\)',value)):
                    raise ValueError('External SVG resources are forbidden.')
                if attr in ('fill','stroke','stop-color') and not (re.fullmatch(r'#[0-9a-fA-F]{3,8}|none|currentColor|[a-zA-Z]+|url\(#[A-Za-z_][A-Za-z0-9_-]*\)',value)):
                    raise ValueError('Unsupported SVG paint.')
        for axis in ('width','height'):
            try:value=float(root.attrib[axis])
            except (KeyError,ValueError):raise ValueError('SVG requires numeric width and height.') from None
            if not 0<value<=4096:raise ValueError('SVG dimensions exceed 4096 pixels.')
    else:raise ValueError('Only static SVG and PNG assets are supported.')


@dataclass
class Skin:
    manifest: dict
    assets: dict
    builtin: bool = False

    @property
    def id(self):return self.manifest['id']


def validate(manifest,assets):
    if not isinstance(manifest,dict) or manifest.get('format')!=FORMAT:raise ValueError('Unsupported skin manifest format.')
    if set(manifest)-{'format','id','name','version','author','license','description','font','colors','surfaces'}:raise ValueError('Unknown manifest fields; executable/style extensions are not supported.')
    if not isinstance(manifest.get('id'),str) or not IDENTIFIER.fullmatch(manifest['id']):raise ValueError('Invalid skin identifier.')
    for field in ('name','version','author','license'):
        if not isinstance(manifest.get(field),str) or not 0<len(manifest[field])<=200:raise ValueError('Skin requires bounded name, version, author and license strings.')
    if not isinstance(manifest.get('description',''),str) or len(manifest.get('description',''))>1000:raise ValueError('Invalid skin description.')
    font=manifest.get('font',{})
    if not isinstance(font,dict) or set(font)-{'family','size'}:raise ValueError('Invalid font settings.')
    if not isinstance(font.get('family','DejaVu Sans'),str) or not re.fullmatch(r'[A-Za-z0-9 -]{1,80}',font.get('family','DejaVu Sans')):raise ValueError('Use an installed font family name; font files are not supported.')
    if type(font.get('size',13)) is not int or not 11<=font.get('size',13)<=24:raise ValueError('Body font size must be 11–24 pixels.')
    colors=manifest.get('colors',{})
    if not isinstance(colors,dict) or set(colors)-PALETTE:raise ValueError('Unknown palette color.')
    for value in colors.values():_color(value,{})
    surfaces=manifest.get('surfaces',{})
    if not isinstance(surfaces,dict) or set(surfaces)-SELECTORS.keys():raise ValueError('Unknown skin surface/state.')
    for surface in surfaces.values():
        if not isinstance(surface,dict) or set(surface)-{'background','foreground','border','texture','gradient'}:raise ValueError('Unknown surface property; raw CSS is not accepted.')
        for prop in ('background','foreground','border'):
            if prop in surface:_color(surface[prop],colors)
        if 'gradient' in surface:
            gradient=surface['gradient']
            if not isinstance(gradient,list) or not 2<=len(gradient)<=4:raise ValueError('Gradients need 2–4 colors.')
            for color in gradient:_color(color,colors)
        if 'texture' in surface:
            if not isinstance(surface['texture'],str) or surface['texture'] not in assets:raise ValueError('Missing surface texture asset.')
        if sum(prop in surface for prop in ('background','gradient','texture'))>1:raise ValueError('Choose background, gradient or texture for each surface.')
    if len(assets)>32 or sum(map(len,assets.values()))>MAX_TOTAL:raise ValueError('Too many or oversized skin assets.')
    for name,raw in assets.items():_asset(name,raw)
    return Skin(manifest,assets)


def load_package(path):
    if Path(path).stat().st_size>MAX_TOTAL:raise ValueError('Skin package exceeds 8 MB.')
    try:
        with zipfile.ZipFile(path) as archive:
            entries=archive.infolist();names=[_path(e.filename) for e in entries]
            if len(entries)>33 or len(names)!=len(set(names)) or sum(e.file_size for e in entries)>MAX_TOTAL:raise ValueError('Duplicate, oversized or excessive skin entries.')
            for entry in entries:
                mode=entry.external_attr>>16
                if (stat.S_IFMT(mode) and not stat.S_ISREG(mode)) or entry.flag_bits&1:raise ValueError('Skin entries must be unencrypted regular files; links are forbidden.')
                if entry.file_size>(65536 if entry.filename=='manifest.json' else MAX_ASSET):raise ValueError('Skin entry exceeds size limit.')
            if 'manifest.json' not in names:raise ValueError('Missing manifest.json.')
            manifest=json.loads(archive.read('manifest.json'))
            assets={name:archive.read(name) for name in names if name!='manifest.json'}
            return validate(manifest,assets)
    except (zipfile.BadZipFile,KeyError,json.JSONDecodeError,UnicodeError) as error:raise ValueError('Invalid skin package.') from error


def load_builtin(identifier):
    if not IDENTIFIER.fullmatch(identifier):raise ValueError('Invalid skin identifier.')
    root=BUILTINS/identifier
    manifest=json.loads((root/'manifest.json').read_text())
    assets={p.relative_to(root).as_posix():p.read_bytes() for p in (root/'assets').glob('*') if p.is_file()}
    skin=validate(manifest,assets);skin.builtin=True
    return skin


def export_package(skin,path):
    validate(skin.manifest,skin.assets)
    path=Path(path).absolute()
    if path.suffix!='.gafawskin':raise ValueError('Choose a .gafawskin filename.')
    if any(p.is_symlink() for p in path.parents):raise ValueError('Skin output must not traverse symlinks.')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream,zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('manifest.json',json.dumps(skin.manifest,indent=2))
        for name,raw in skin.assets.items():archive.writestr(name,raw)


class PreparedSkin:
    def __init__(self,skin):
        validate(skin.manifest,skin.assets)
        self.directory=tempfile.TemporaryDirectory(prefix='gafaw-skin-')
        root=Path(self.directory.name)
        try:
            for name,raw in skin.assets.items():
                path=root/name;path.parent.mkdir(exist_ok=True,parents=True);path.write_bytes(raw)
            colors={'background':'#181d20','text':'#e0e8e9','muted':'#b4c2c5','accent':'#9af7ab','focus':'#b4f5b0',**skin.manifest.get('colors',{})}
            font=skin.manifest.get('font',{})
            css=(BUILTINS/'base.css').read_text()
            css+=f'\n* {{ font-family: "{font.get("family","DejaVu Sans")}"; font-size: {font.get("size",13)}px; }}\n'
            css+=f'window, notebook {{background:{colors["background"]};color:{colors["text"]};}}\n.subtitle {{color:{colors["muted"]};}}\n.metric, .eyebrow {{color:{colors["accent"]};}}\n'
            for name,surface in skin.manifest.get('surfaces',{}).items():
                properties=[]
                for prop in ('background','foreground','border'):
                    if prop in surface:properties.append({'background':'background','foreground':'color','border':'border-color'}[prop]+':'+_color(surface[prop],colors)+';')
                if 'gradient' in surface:properties.append('background-image:linear-gradient(to bottom,'+','.join(_color(c,colors) for c in surface['gradient'])+');')
                if 'texture' in surface:properties.append('background-image:url("'+(root/surface['texture']).as_uri()+'");')
                css+=SELECTORS[name]+' {'+''.join(properties)+'}\n'
            # Imported skins cannot remove focus rings, alter widget visibility, or change interaction.
            css+=f'button:focus, entry:focus, spinbutton:focus, combobox:focus, textview:focus, checkbutton:focus, scale:focus, notebook tab:focus, list row:focus {{outline:2px solid {colors["focus"]};outline-offset:2px;}}\n'
            self.css=css.encode()
        except Exception:
            self.close();raise

    def close(self):self.directory.cleanup()


class SkinLibrary:
    def __init__(self,root):self.root=Path(root).absolute()

    def _check_root(self,create=False):
        if any(p.is_symlink() for p in (self.root,*self.root.parents)):raise ValueError('Skin library must not traverse symlinks.')
        if create:self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.root.exists():
            if not self.root.is_dir():raise ValueError('Skin library must be a directory.')
            for p in self.root.iterdir():
                if p.is_symlink() or not p.is_file() or p.name!='selection.json' and not p.name.endswith('.gafawskin'):raise ValueError('Skin library contains unrelated or unsafe entries; choose a dedicated directory.')

    def list(self):
        self._check_root()
        skins=[load_builtin('black-titanium'),load_builtin('phosphor-night')];errors=[]
        if self.root.exists():
            for path in sorted(self.root.glob('*.gafawskin')):
                try:
                    skin=load_package(path)
                    if skin.id!=path.stem or skin.id in {s.id for s in skins}:raise ValueError('Conflicting skin identifier.')
                    skins.append(skin)
                except (ValueError,OSError) as error:errors.append(f'{path.name}: {error}')
        return skins,errors

    def get(self,identifier):
        if identifier in ('black-titanium','phosphor-night'):return load_builtin(identifier)
        if not isinstance(identifier,str) or not IDENTIFIER.fullmatch(identifier):raise ValueError('Invalid skin identifier.')
        self._check_root();skin=load_package(self.root/(identifier+'.gafawskin'))
        if skin.id!=identifier:raise ValueError('Skin filename/identifier mismatch.')
        return skin

    def selected(self):
        self._check_root();path=self.root/'selection.json'
        if not path.exists():return 'black-titanium'
        if path.stat().st_size>4096:raise ValueError('Oversized skin selection.')
        return self.get(json.loads(path.read_text())['skin']).id

    def select(self,identifier):
        self.get(identifier);self._check_root(create=True)
        # Exclusive temporary file + replace prevents following a selection-file link.
        fd,path=tempfile.mkstemp(prefix='selection-',suffix='.tmp',dir=self.root)
        try:
            with os.fdopen(fd,'w') as stream:json.dump({'skin':identifier},stream)
            os.replace(path,self.root/'selection.json')
        finally:
            if Path(path).exists():Path(path).unlink()

    def install(self,path):
        skin=load_package(path)
        if skin.id in ('black-titanium','phosphor-night'):raise ValueError('Built-in skin identifiers are reserved; give custom skins a new id.')
        self._check_root(create=True)
        export_package(skin,self.root/(skin.id+'.gafawskin'))
        return skin
