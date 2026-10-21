import hashlib
import json
import os
import re
from pathlib import Path
import sqlite3
import stat
import time
import uuid
from .security import redact, reject_secrets

class Store:
    def __init__(self, root):
        requested = Path(root).absolute()
        # Reject link traversal before resolving; never migrate a link target.
        if any(path.is_symlink() for path in (requested, *requested.parents)):
            raise ValueError('Laboratory paths must not traverse symlinks.')
        self.root = requested.resolve()
        if (self.root/'.git').exists() or self.root in (
                Path('/'), Path.home().resolve(), Path(__file__).resolve().parent,
                Path(__file__).resolve().parent.parent):
            raise ValueError('Choose a dedicated OVERMIND laboratory directory, not a home or source directory.')
        entries = self._migration_preflight()
        # No filesystem mutation occurs until the entire preflight succeeds.
        self.root.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.root.chmod(0o700)
        for path, directory in entries:
            path.chmod(0o700 if directory else 0o600)
        marker=self.root/'.overmind-lab'
        if not marker.exists():
            fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as stream:stream.write('OVERMIND laboratory v1\n')
        self._ignore_marker()
        self.db = self.root/'lab.sqlite3'
        fd=os.open(self.db,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:os.fchmod(fd,0o600)
        finally:os.close(fd)
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created REAL, updated REAL, status TEXT, config TEXT, state TEXT);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, time REAL, kind TEXT, message TEXT);
            CREATE TABLE IF NOT EXISTS cloud_calls(id TEXT PRIMARY KEY, run_id TEXT, created REAL, provider TEXT, model TEXT,
            reserved_microusd INTEGER, charged_microusd INTEGER, input_bound INTEGER, output_cap INTEGER,
            input_tokens INTEGER, output_tokens INTEGER, status TEXT, error TEXT);''')

    def _migration_preflight(self):
        """Recognize ownership and validate the whole tree before changing permissions.

        Empty/new directories can be initialized. Legacy installations are recognized
        by both original SQLite schemas, never by their name or ignore file alone.
        """
        if not self.root.exists():return []
        if not self.root.is_dir():raise ValueError('Laboratory path must be a directory.')
        children=list(self.root.iterdir())
        if not children:return []
        def check(path):
            info=path.lstat()
            if stat.S_ISDIR(info.st_mode):return True
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Laboratory entries must be regular unlinked files or directories; symlinks, hardlinks and special files are unsafe.')
            return False
        for path in children:check(path)
        marker=self.root/'.overmind-lab'
        marked=marker.is_file() and marker.stat().st_size<=64 and marker.read_bytes()==b'OVERMIND laboratory v1\n'
        if marker.exists() and not marked:
            raise ValueError('Invalid OVERMIND ownership marker; no permissions were changed.')
        db=self.root/'lab.sqlite3'
        run_ids=set()
        legacy=False
        if db.is_file():
            try:
                # Immutable read-only inspection cannot create journals or change the DB.
                with sqlite3.connect(db.as_uri()+'?mode=ro&immutable=1',uri=True) as c:
                    expected={'runs':['id','created','updated','status','config','state'],
                              'events':['seq','run_id','time','kind','message']}
                    legacy=all([r[1] for r in c.execute('PRAGMA table_info('+table+')')]==columns
                               for table,columns in expected.items())
                    if legacy:run_ids={r[0] for r in c.execute('SELECT id FROM runs')}
            except sqlite3.Error:
                raise ValueError('Unrecognized laboratory database; no permissions were changed.') from None
            if not legacy:raise ValueError('Unrecognized laboratory database schema; no permissions were changed.')
        if not (marked or legacy):
            raise ValueError('Directory is not recognized as OVERMIND-owned. Choose a new or empty dedicated directory; no permissions were changed.')
        files={'.overmind-lab','.gitignore','lab.sqlite3','lab.sqlite3-journal',
               'lab.sqlite3-wal','lab.sqlite3-shm','worker.lock'}
        for path in children:
            if path.is_dir():
                if path.name not in run_ids and not re.fullmatch(r'[0-9a-f]{12}',path.name):
                    raise ValueError('Unrecognized directory in laboratory; no permissions were changed.')
            elif path.name not in files:
                raise ValueError('Unrecognized file in laboratory; no permissions were changed.')
        entries=[]
        def failed(error):raise error
        for directory,dirs,files in os.walk(self.root,followlinks=False,onerror=failed):
            for name in dirs+files:
                path=Path(directory)/name
                entries.append((path,check(path)))
        return entries

    def _ignore_marker(self):
        path=self.root/'.gitignore'
        existing=path.read_bytes() if path.exists() else b''
        marker=b'# OVERMIND private laboratory data\n*\n'
        if not existing.endswith(marker):
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'ab') as stream:
                os.fchmod(stream.fileno(),0o600)
                if existing and not existing.endswith(b'\n'):stream.write(b'\n')
                stream.write(marker)

    def _path(self,rid,name):
        if any(not isinstance(part,str) or part in ('','.','..') or Path(part).name!=part for part in (rid,name)):
            raise ValueError('Invalid artifact name.')
        directory=self.root/rid
        if directory.is_symlink() or (directory/name).is_symlink():
            raise ValueError('Laboratory entries must not be symlinks.')
        return directory/name

    def lock(self):
        fd=os.open(self.root/'worker.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
        os.fchmod(fd,0o600)
        return os.fdopen(fd,'a')

    def connect(self):
        c = sqlite3.connect(self.db,timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def create(self, config, dataset):
        reject_secrets(config)
        reject_secrets(dataset)
        config=redact(config)
        is_sft=dataset.get('format')=='gafaw.sft.v1'
        if (config.get('student',{}).get('kind')=='local_lora')!=is_sft:
            raise ValueError('Local LoRA requires reviewed instruction/response data; classifier/prompt experiments require labeled classification data.')
        original=None
        checkpoint=config.get('student',{}).get('checkpoint')
        if checkpoint:
            from .model import TextStudent
            source=Path(checkpoint)
            if source.stat().st_size>4_000_000: raise ValueError('Checkpoint exceeds 4 MB limit.')
            original=json.loads(source.read_text())
            model=TextStudent.restore(original)
            if model.labels!=dataset['labels']:
                raise ValueError('Checkpoint labels must match dataset labels in the same order.')
        rid = uuid.uuid4().hex[:12]
        (self.root/rid).mkdir(mode=0o700)
        self.artifact(rid,'dataset.json',dataset)
        if original is not None: self.artifact(rid,'original-student.json',original)
        with self.connect() as c:
            c.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(rid,time.time(),time.time(),'ready',json.dumps(config),json.dumps({'phase':'inspect','calls':0,'epoch':0})))
        self.event(rid,'system','Experiment created. Dataset snapshot sealed; test examples are excluded from mentor context.')
        return rid

    def get(self,rid):
        with self.connect() as c: row = c.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
        if not row: raise ValueError('Unknown experiment.')
        row = dict(row)
        row['config'],row['state'] = json.loads(row['config']),json.loads(row['state'])
        return row

    def list(self):
        with self.connect() as c: return [dict(x) for x in c.execute('SELECT id,created,updated,status,config,state FROM runs ORDER BY created DESC')]

    def update(self,rid,*,status=None,state=None):
        with self.connect() as c:
            if status is not None: c.execute('UPDATE runs SET status=?,updated=? WHERE id=?',(redact(status),time.time(),rid))
            if state is not None: reject_secrets(state)
            if state is not None: c.execute('UPDATE runs SET state=?,updated=? WHERE id=?',(json.dumps(redact(state)),time.time(),rid))

    def event(self,rid,kind,message):
        with self.connect() as c: c.execute('INSERT INTO events(run_id,time,kind,message) VALUES(?,?,?,?)',(rid,time.time(),redact(kind),redact(str(message))[:20000]))

    def events(self,rid):
        with self.connect() as c: return [dict(x) for x in c.execute('SELECT * FROM events WHERE run_id=? ORDER BY seq',(rid,))]

    def artifact(self,rid,name,data):
        reject_secrets(data)
        path = self._path(rid,name)
        raw = json.dumps(redact(data),indent=2,allow_nan=False).encode()
        tmp = path.with_suffix('.tmp')
        fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:
            os.fchmod(f.fileno(),0o600)
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        return hashlib.sha256(raw).hexdigest()

    def read(self,rid,name):
        return json.loads(self._path(rid,name).read_text())

    def reserve_cloud(self,rid,kind,model,limits,input_bound,output_cap):
        from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
        from .cloud import BudgetExceeded
        budget=int((Decimal(limits['budget_usd'])*1_000_000).to_integral_value(rounding=ROUND_FLOOR))
        reserved=int((Decimal(input_bound)*Decimal(limits['input_usd_per_million'])+
                      Decimal(output_cap)*Decimal(limits['output_usd_per_million'])).to_integral_value(rounding=ROUND_CEILING))
        call_id=uuid.uuid4().hex
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute("SELECT 1 FROM cloud_calls WHERE run_id=? AND status='overrun'",(rid,)).fetchone():
                raise BudgetExceeded('Cloud dispatch disabled after a reservation overrun.')
            used=c.execute('SELECT COALESCE(SUM(charged_microusd),0) FROM cloud_calls WHERE run_id=?',(rid,)).fetchone()[0]
            if used+reserved>budget:raise BudgetExceeded('Cloud budget cannot cover the next conservative reservation. No request was sent.')
            c.execute('INSERT INTO cloud_calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (call_id,rid,time.time(),redact(kind),redact(model),reserved,reserved,input_bound,output_cap,None,None,'reserved',None))
        return call_id

    def settle_cloud(self,call_id,limits,usage,error=False):
        from decimal import Decimal, ROUND_CEILING
        from .cloud import BudgetExceeded
        overrun=False
        with self.connect() as c:
            row=c.execute('SELECT * FROM cloud_calls WHERE id=?',(call_id,)).fetchone()
            if not row or row['status']!='reserved':raise ValueError('Cloud reservation is missing or already settled.')
            if usage is None:
                c.execute('UPDATE cloud_calls SET status=?,error=? WHERE id=?',('uncertain','Usage unavailable; full reservation retained.',call_id))
            else:
                i,o=usage['input_tokens'],usage['output_tokens']
                if type(i) is not int or type(o) is not int or i<0 or o<0:raise ValueError('Invalid cloud token usage.')
                charge=int((Decimal(i)*Decimal(limits['input_usd_per_million'])+Decimal(o)*Decimal(limits['output_usd_per_million'])).to_integral_value(rounding=ROUND_CEILING))
                overrun=i>row['input_bound'] or o>row['output_cap']
                c.execute('UPDATE cloud_calls SET charged_microusd=?,input_tokens=?,output_tokens=?,status=?,error=? WHERE id=?',
                    (max(charge,row['reserved_microusd']) if overrun else charge,i,o,'overrun' if overrun else 'error_usage' if error else 'completed',
                     'Provider usage exceeded reservation bounds; stop all further dispatch.' if overrun else None,call_id))
        if overrun:raise BudgetExceeded('Provider usage exceeded the reserved token bounds. Cloud dispatch stopped; inspect account billing.')

    def billing(self,rid):
        with self.connect() as c:
            rows=[dict(x) for x in c.execute('SELECT * FROM cloud_calls WHERE run_id=? ORDER BY created',(rid,))]
        return {'charged_or_reserved_usd':sum(x['charged_microusd'] for x in rows)/1_000_000,
                'input_tokens':sum(x['input_tokens'] or 0 for x in rows),'output_tokens':sum(x['output_tokens'] or 0 for x in rows),
                'uncertain_calls':sum(x['status'] in ('reserved','uncertain') for x in rows),'calls':rows}
