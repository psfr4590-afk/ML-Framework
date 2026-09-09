from __future__ import annotations
import json,os
from datetime import datetime,timezone
from pathlib import Path
from .config import DATASETS,load_groups
class DatasetStore:
 def __init__(self): DATASETS.mkdir(parents=True,exist_ok=True)
 def _ids(self): return sorted(int(p.name[8:]) for p in DATASETS.glob('dataset_*') if p.is_dir() and p.name[8:].isdigit())
 def path(self,did): return DATASETS/f'dataset_{int(did)}'
 def get(self,did):
  p=self.path(did)/'dataset.json'; return json.loads(p.read_text()) if p.exists() else None
 def list(self): return [self.get(i) for i in self._ids()]
 def create(self,name,description='',group_id=None,group_config=None):
  gid=group_id or (group_config or {}).get('id','custom'); ids=self._ids(); did=(ids[-1]+1 if ids else 1); root=self.path(did); root.mkdir(parents=True,exist_ok=True)
  for s in ('raw','cleaned','dedup','weighted','tokenized','shards','checkpoints','model','logs','metrics','errors','output'): (root/s).mkdir(parents=True,exist_ok=True)
  meta={'id':did,'name':name,'description':description,'group_id':gid,'status':'READY','stages':{x:'idle' for x in ('crawl','clean','dedup','weight','tokenize','shard','train','export')},'events':[],'stats':{'documents':0,'files':0,'bytes':0}}
  self._write(did,meta); return meta
 def _write(self,did,d):
  p=self.path(did)/'dataset.json'; tmp=p.with_suffix('.tmp'); tmp.write_text(json.dumps(d,indent=2),encoding='utf-8'); os.replace(tmp,p)
 def ensure_seed_datasets(self):
  groups=load_groups(); existing={d['group_id'] for d in self.list()}
  for g in groups:
   if g.get('id') not in existing: self.create(g.get('name',g['id']),group_id=g['id'],group_config=g)
  return self.list()
 def refresh_pipeline_state(self,did):
  d=self.get(did)
  if not d: raise KeyError(did)
  out=dict(d); tok=self.path(did)/'output'/'tokenizer'/'tokenizer.json'
  if tok.is_file(): out['stages']=dict(out['stages']); out['stages']['tokenize']='complete'
  return out
 def update(self,did,**kw): d=self.get(did); d.update(kw); self._write(did,d); return d
 def event(self,did,event,data=None): d=self.get(did); d['events'].append({'ts':datetime.now(timezone.utc).isoformat(),'event':event,'data':data or {}}); self._write(did,d)
 def crawl_stats(self,did): return self.get(did)['stats']
 def crawl_domains(self,did): return []
 def crawl_log(self,did):
  p=self.path(did)/'logs'/'command-center.log'; return p.read_text(encoding='utf-8') if p.exists() else ''
