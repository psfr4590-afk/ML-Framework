from __future__ import annotations
import json,os,platform,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
def utc_now(): return datetime.now(timezone.utc).isoformat()
def is_project_root(path): return path.is_dir() and all((path/x).exists() for x in ("run_pipeline.py","bootstrap.py","requirements.txt","pipeline","config"))
def discover_project_root(start=None):
 start=(start or Path(__file__).resolve().parent).resolve()
 for p in (start,*start.parents):
  if is_project_root(p): return p
 raise RuntimeError(f"Unable to locate Model Lab project root from {start}")
def normalize_path(p): return str(Path(p).resolve())
def executable_version(exe):
 try:
  r=subprocess.run([str(exe),"--version"],capture_output=True,text=True,timeout=10,check=False); lines=(r.stdout or r.stderr).strip().splitlines(); return lines[0] if lines else None
 except Exception:return None
def all_executables(names):
 out={}
 for n in names:
  p=shutil.which(n); out[n]={"status":"FOUND" if p else "MISSING","path":normalize_path(p) if p else None,"version":executable_version(Path(p)) if p else None}
 return out
def python_state(): return {"status":"VERIFIED","executable":normalize_path(sys.executable),"version":platform.python_version(),"implementation":platform.python_implementation()}
def write_environment_state(root,state):
 d=root/".runtime"; d.mkdir(parents=True,exist_ok=True); payload={"schema":2,"updated_at":utc_now(),"project_root":str(root.resolve()),"python":python_state(),"environment":{"os":platform.platform(),"cwd_at_probe":str(Path.cwd().resolve()),"path":os.environ.get("PATH","")},"tools":state.get("tools",{}),"python_packages":state.get("python_packages",{}),"capabilities":state.get("capabilities",{}),"events":state.get("events",[])}; path=d/"environment.json"; tmp=path.with_suffix(".tmp"); tmp.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8"); os.replace(tmp,path); return path
