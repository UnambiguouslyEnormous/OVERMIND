import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.db = self.root/'lab.sqlite3'
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, created REAL, updated REAL, status TEXT, config TEXT, state TEXT);
            CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, time REAL, kind TEXT, message TEXT);''')

    def connect(self):
        c = sqlite3.connect(self.db,timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def create(self, config, dataset):
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
            if state is not None: c.execute('UPDATE runs SET state=?,updated=? WHERE id=?',(json.dumps(state),time.time(),rid))

    def event(self,rid,kind,message):
        with self.connect() as c: c.execute('INSERT INTO events(run_id,time,kind,message) VALUES(?,?,?,?)',(rid,time.time(),kind,str(message)[:20000]))

    def events(self,rid):
        with self.connect() as c: return [dict(x) for x in c.execute('SELECT * FROM events WHERE run_id=? ORDER BY seq',(rid,))]

    def artifact(self,rid,name,data):
        if Path(name).name != name or Path(rid).name != rid: raise ValueError('Invalid artifact name.')
        path = self.root/rid/name
        raw = json.dumps(data,indent=2,allow_nan=False).encode()
        tmp = path.with_suffix('.tmp')
        with open(tmp,'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        return hashlib.sha256(raw).hexdigest()

    def read(self,rid,name):
        return json.loads((self.root/rid/name).read_text())
