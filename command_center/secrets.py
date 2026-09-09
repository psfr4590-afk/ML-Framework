from __future__ import annotations
import base64,json,os
from datetime import datetime,timezone
from pathlib import Path
from threading import RLock
from .config import ROOT
LOCK=RLock(); STORE_PATH=ROOT/'.runtime'/'credentials.json'
def _enc(s):
 from cryptography.fernet import Fernet
 key=os.environ.get('PIPELINE_CREDENTIAL_KEY')
 if not key: raise RuntimeError('PIPELINE_CREDENTIAL_KEY is required')
 return base64.b64encode(Fernet(key.encode()).encrypt(s.encode())).decode()
def _dec(s):
 from cryptography.fernet import Fernet
 key=os.environ.get('PIPELINE_CREDENTIAL_KEY')
 if not key: raise RuntimeError('PIPELINE_CREDENTIAL_KEY is required')
 return Fernet(key.encode()).decrypt(base64.b64decode(s)).decode()
def _now(): return datetime.now(timezone.utc).isoformat()
class CredentialStore:
 def __init__(self,path=STORE_PATH): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
 def _load(self):
  if not self.path.exists(): return {'version':1,'credentials':{}}
  d=json.loads(self.path.read_text(encoding='utf-8')); d.setdefault('credentials',{}); return d
 def _save(self,d):
  tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(d,indent=2),encoding='utf-8'); os.replace(tmp,self.path)
  try: os.chmod(self.path,0o600)
  except OSError: pass
 def list(self):
  with LOCK:
   out=[]
   for n,x in sorted(self._load()['credentials'].items()):
    out.append({'name':n,'provider':x.get('provider','custom'),'type':x.get('type','token'),'env_var':x.get('env_var',''),'description':x.get('description',''),'identity':x.get('identity',''),'updated_at':x.get('updated_at'),'stored':True,'environment_set':bool(x.get('env_var') and os.environ.get(x['env_var']))})
   return out
 def set(self,name,secret,provider='custom',kind='token',env_var='',description='',identity=''):
  if not name or not secret: raise ValueError('credential name and secret are required')
  with LOCK:
   d=self._load(); old=d['credentials'].get(name,{})
   d['credentials'][name]={'provider':provider,'type':kind,'env_var':env_var,'description':description,'identity':identity,'secret':_enc(secret),'created_at':old.get('created_at',_now()),'updated_at':_now()}
   self._save(d); return next(x for x in self.list() if x['name']==name)
 def delete(self,name):
  with LOCK:
   d=self._load()
   if name not in d['credentials']: return False
   del d['credentials'][name]; self._save(d); return True
 def reveal(self,name):
  with LOCK:
   x=self._load()['credentials'].get(name)
   if not x: raise KeyError(name)
   return _dec(x['secret'])
 def environment(self):
  with LOCK: return {x['env_var']:_dec(x['secret']) for x in self._load()['credentials'].values() if x.get('env_var')}
 def test(self,name):
  s=self.reveal(name); x=next(v for v in self.list() if v['name']==name); return {'ok':bool(s),'name':name,'provider':x['provider'],'env_var':x['env_var'],'length':len(s)}
credentials=CredentialStore()
