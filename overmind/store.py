import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid
from .security import redact, reject_secrets

class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.db = self.root/'lab.sqlite3'
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created REAL, updated REAL, status TEXT, config TEXT, state TEXT);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, time REAL, kind TEXT, message TEXT);
            CREATE TABLE IF NOT EXISTS cloud_calls(id TEXT PRIMARY KEY, run_id TEXT, created REAL, provider TEXT, model TEXT,
            reserved_microusd INTEGER, charged_microusd INTEGER, input_bound INTEGER, output_cap INTEGER,
            input_tokens INTEGER, output_tokens INTEGER, status TEXT, error TEXT);''')

    def connect(self):
        c = sqlite3.connect(self.db,timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def create(self, config, dataset):
        reject_secrets(config)
        config=redact(config)
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
        (self.root/rid).mkdir()
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
            if status is not None: c.execute('UPDATE runs SET status=?,updated=? WHERE id=?',(status,time.time(),rid))
            if state is not None: c.execute('UPDATE runs SET state=?,updated=? WHERE id=?',(json.dumps(redact(state)),time.time(),rid))

    def event(self,rid,kind,message):
        with self.connect() as c: c.execute('INSERT INTO events(run_id,time,kind,message) VALUES(?,?,?,?)',(rid,time.time(),kind,redact(str(message))[:20000]))

    def events(self,rid):
        with self.connect() as c: return [dict(x) for x in c.execute('SELECT * FROM events WHERE run_id=? ORDER BY seq',(rid,))]

    def artifact(self,rid,name,data):
        if Path(name).name != name or Path(rid).name != rid: raise ValueError('Invalid artifact name.')
        path = self.root/rid/name
        raw = json.dumps(redact(data),indent=2,allow_nan=False).encode()
        tmp = path.with_suffix('.tmp')
        with open(tmp,'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        return hashlib.sha256(raw).hexdigest()

    def read(self,rid,name):
        return json.loads((self.root/rid/name).read_text())

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
                (call_id,rid,time.time(),kind,model,reserved,reserved,input_bound,output_cap,None,None,'reserved',None))
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
