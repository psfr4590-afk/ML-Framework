from __future__ import annotations
import base64,json,os
from pathlib import Path
from threading import RLock
from cryptography.fernet import Fernet
from .config import ROOT
LOCK=RLock(); STORE_PATH=ROOT/".runtime"/"credentials.json"
def _key():
 k=os.environ.get("PIPELINE_CREDENTIAL_KEY","")
 if not k: raise RuntimeError("PIPELINE_CREDENTIAL_KEY is required on non-Windows hosts")
 return Fernet(k.encode())
class CredentialStore:
 def __init__(self,path:Path=STORE_PATH): self.path=path; self.path.parent.mkdir(parents=True,exist_ok=True)
 def _load(self):
  if not self.path.exists(): return {"version":1,"credentials":{}}
  return json.loads(self.path.read_text(encoding="utf-8"))
 def _save(self,d):
  self.path.parent.mkdir(parents=True,exist_ok=True); tmp=self.path.with_suffix(".tmp"); tmp.write_text(json.dumps(d,indent=2),encoding="utf-8"); os.replace(tmp,self.path)
 def set(self,name,secret,provider="custom",kind="token",env_var="",description="",identity=""):
  with LOCK:
   d=self._load(); f=_key(); d["credentials"][name]={"secret":base64.b64encode(f.encrypt(secret.encode())).decode(),"provider":provider,"type":kind,"env_var":env_var,"description":description,"identity":identity}; self._save(d)
   return {"name":name,"provider":provider,"type":kind,"env_var":env_var,"description":description,"identity":identity,"stored":True}
 def reveal(self,name):
  d=self._load()
  if name not in d.get("credentials",{}): raise KeyError(name)
  return _key().decrypt(base64.b64decode(d["credentials"][name]["secret"])).decode()
 def list(self):
  d=self._load(); out=[]
  for n,i in sorted(d.get("credentials",{}).items()): out.append({"name":n,"provider":i.get("provider","custom"),"type":i.get("type","token"),"env_var":i.get("env_var",""),"description":i.get("description",""),"identity":i.get("identity",""),"stored":True,"environment_set":bool(i.get("env_var") and os.environ.get(i.get("env_var")))})
  return out
 def environment(self):
  env={}
  for n,i in self._load().get("credentials",{}).items():
   if i.get("env_var"): env[i["env_var"]]=self.reveal(n)
  return env
 def delete(self,name):
  with LOCK:
   d=self._load()
   if name not in d.get("credentials",{}): return False
   del d["credentials"][name]; self._save(d); return True
 def test(self,name):
  value=self.reveal(name); return {"ok":bool(value),"name":name}
credentials=CredentialStore()
