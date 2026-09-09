#!/usr/bin/env python3
from __future__ import annotations
import argparse, platform, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def run(cmd:list[str])->int:
    print("$", " ".join(map(str,cmd)))
    return subprocess.run(cmd,cwd=ROOT,text=True,check=False).returncode
def main()->int:
    p=argparse.ArgumentParser(description="Model Lab production release gate")
    p.add_argument("--bootstrap-native",action="store_true")
    p.add_argument("--skip-tests",action="store_true")
    a=p.parse_args()
    if a.skip_tests: print("RELEASE GATE FAILED: --skip-tests is not allowed."); return 2
    failures=[]
    if run([sys.executable,"-m","compileall","-q","."]): failures.append("compileall")
    if run([sys.executable,"-m","pytest","-q"]): failures.append("pytest")
    if run([sys.executable,"run_pipeline.py","--doctor"]): failures.append("doctor")
    if failures:
        print("RELEASE GATE FAILED:",", ".join(failures)); print("Platform:",platform.platform()); return 2
    print("RELEASE GATE PASSED"); return 0
if __name__=="__main__": raise SystemExit(main())
