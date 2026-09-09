from __future__ import annotations
import argparse,json
from .service import list_datasets,start,halt

def main(argv=None):
 p=argparse.ArgumentParser(description="Model Lab command center"); sub=p.add_subparsers(dest="cmd"); sub.add_parser("datasets"); r=sub.add_parser("run"); r.add_argument("dataset_id",type=int); r.add_argument("stage"); s=sub.add_parser("stop"); s.add_argument("dataset_id",type=int); a=p.parse_args(argv)
 if a.cmd=="datasets": print(json.dumps(list_datasets(),indent=2))
 elif a.cmd=="run": print(json.dumps(start(a.dataset_id,a.stage),indent=2))
 elif a.cmd=="stop": print(json.dumps(halt(a.dataset_id),indent=2))
 else:p.print_help()
 return 0
