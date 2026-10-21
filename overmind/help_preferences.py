"""Allowlisted, bounded local UI preferences. No experiment data or executable content."""
import json
import os
from pathlib import Path
import tempfile
from .help_guide import TUTORIALS


def defaults():
    return {'stanley':True,'sarcasm':True,'reduced_motion':False,
            'guide':{'width':980,'height':740,'x':None,'y':None,'ontop':False},
            'companion':{'width':420,'height':530,'x':None,'y':None,'ontop':False},'tutorials':{}}


def checked(raw):
    out=defaults()
    if not isinstance(raw,dict):return out
    for key in ('stanley','sarcasm','reduced_motion'):
        if type(raw.get(key)) is bool:out[key]=raw[key]
    for key in ('guide','companion'):
        saved=raw.get(key,{})
        if not isinstance(saved,dict):continue
        for field,low,high in (('width',340,2400),('height',320,1800),('x',-32768,32768),('y',-32768,32768)):
            value=saved.get(field)
            if type(value) is int:out[key][field]=max(low,min(high,value))
        if type(saved.get('ontop')) is bool:out[key]['ontop']=saved['ontop']
    tutorials=raw.get('tutorials',{})
    if isinstance(tutorials,dict):
        for key,(_,steps) in TUTORIALS.items():
            saved=tutorials.get(key)
            if not isinstance(saved,dict):continue
            step=saved.get('step',0)
            out['tutorials'][key]={'step':max(0,min(len(steps)-1,step)) if type(step) is int else 0,
                'completed':saved.get('completed') is True,
                'skipped':sorted({i for i in saved.get('skipped',[]) if type(i) is int and 0<=i<len(steps)}) if isinstance(saved.get('skipped',[]),list) else []}
    return out


class Preferences:
    def __init__(self,path):
        self.path=Path(path).absolute();self.error=None
        try:
            self._paths()
            if self.path.exists():
                if not self.path.is_file() or self.path.stat().st_size>32768:raise ValueError('Invalid help preference file.')
                self.data=checked(json.loads(self.path.read_text()))
            else:self.data=defaults()
        except (OSError,ValueError,RecursionError):self.data=defaults();self.error='Help preferences could not be read; using session defaults.'

    def _paths(self):
        if any(p.is_symlink() for p in (self.path,*self.path.parents)):raise ValueError('Help preferences must not traverse symlinks.')

    def save(self):
        temporary=None
        try:
            self._paths();self.data=checked(self.data)
            self.path.parent.mkdir(parents=True,exist_ok=True)
            fd,temporary=tempfile.mkstemp(prefix='gafaw-help-',suffix='.tmp',dir=self.path.parent)
            with os.fdopen(fd,'w') as stream:json.dump(self.data,stream)
            os.replace(temporary,self.path);self.error=None;return True
        except (OSError,ValueError):self.error='Help preferences could not be saved; changes remain active for this session.';return False
        finally:
            if temporary and Path(temporary).exists():Path(temporary).unlink()


class Navigation:
    """Article history independent of search results and tutorial progress."""
    def __init__(self):self.current='guide.start';self.history=[]
    def visit(self,key):
        from .help_guide import ARTICLES
        if key not in ARTICLES:raise KeyError(key)
        if self.current!=key:self.history.append(self.current);self.history=self.history[-100:];self.current=key
    def back(self):
        if self.history:self.current=self.history.pop()
        return self.current
