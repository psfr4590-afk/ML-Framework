from __future__ import annotations
import os,subprocess,sys,threading
from .config import ROOT
from .secrets import credentials
from .store import store
RUNS={}; LOCK=threading.RLock()
def _run(did,stage):
 d=store.get(did); stages=dict(d["stages"]); stages[stage]="running"; store.update(did,stages=stages,status="RUNNING")
 env=os.environ.copy(); env.update({"DATASET_ID":str(did),"DATASET_DIR":str(store.path(did)),"PROJECT_ROOT":str(ROOT)}); 
 try: env.update(credentials.environment())
 except Exception: pass
 cmd=[sys.executable,str(ROOT/"run_pipeline.py"),"--dataset-id",str(did),"--stages",stage]
 logp=store.path(did)/"logs"/"command-center.log"; logp.parent.mkdir(parents=True,exist_ok=True)
 try:
  p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding="utf-8",errors="replace")
  with LOCK: RUNS[did]=p
  for line in p.stdout or []:
   with logp.open("a",encoding="utf-8") as f:f.write(line.rstrip()+"\n")
  code=p.wait(); stages=dict(store.get(did)["stages"]); stages[stage]="complete" if code==0 else "failed"; store.update(did,stages=stages,status="ERROR" if code else store.get(did).get("status","RUNNING"))
 finally:
  with LOCK: RUNS.pop(did,None)
  store.refresh_pipeline_state(did)
def start_stage(did,stage):
 if stage not in {"crawl","clean","dedup","weight","tokenize","shard","train","export"}: raise ValueError(stage)
 if not store.get(did): raise ValueError(f"Unknown dataset {did}")
 with LOCK:
  if did in RUNS and RUNS[did] is not None and RUNS[did].poll() is None: raise RuntimeError(f"Dataset {did} already has a running pipeline stage")
  RUNS[did]=None; threading.Thread(target=_run,args=(did,stage),daemon=True).start()
 return {"started":True,"dataset_id":did,"stage":stage}
def stop(did):
 with LOCK:p=RUNS.get(did)
 if p is None or p.poll() is not None:return False
 p.terminate(); return True
