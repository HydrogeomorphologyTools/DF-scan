#!/usr/bin/env python3
"""MSF – Command Line Interface (PyQt-free)"""
import argparse, json, sys
try:
    from . import msf_engine as core
except ImportError:
    import msf_engine as core
except Exception as e:
    print(f"\nERROR importing msf_engine.py: {e}\n")
    sys.exit(1)

TRUE, FALSE = {"1","true","yes","on","y","t"}, {"0","false","no","off","n","f"}
def coerce(v:str):
    s=v.strip().lower()
    if s in TRUE: return True
    if s in FALSE: return False
    try:
        return float(v) if "." in v else int(v)
    except ValueError:
        return v
def apply_dict(cfg_cls,d:dict):
    miss=[]
    for k,v in d.items():
        if hasattr(cfg_cls,k): setattr(cfg_cls,k,v)
        else: miss.append(k)
    return miss
def build_from_json(path:str)->dict:
    with open(path,"r",encoding="utf-8") as f:
        data=json.load(f)
    if not isinstance(data,dict):
        raise ValueError("Config JSON must be an object at top level")
    return data
def parse_args():
    p=argparse.ArgumentParser(description="MSF – CLI wrapper")
    p.add_argument("--config",default=None, help="Path to a JSON config file")
    p.add_argument("--set",action="append",default=[],help="Override KEY=VALUE (repeatable)")
    p.add_argument("--dump-config",default=None, help="Write the resolved config to JSON")
    return p.parse_args()
def main():
    args=parse_args()
    resolved={k:getattr(core.Config,k) for k in dir(core.Config)
              if k.isupper() and not k.startswith("__")}
    if args.config:
        resolved.update(build_from_json(args.config))
    for pair in args.set:
        if "=" not in pair:
            print(f"Ignoring malformed --set '{pair}'")
            continue
        k,v=pair.split("=",1)
        resolved[k.strip()]=coerce(v)
    missing=apply_dict(core.Config,resolved)
    if missing:
        print("\n⚠ Unknown keys ignored:")
        for k in missing: print(" ",k)
    if args.dump_config:
        with open(args.dump_config,"w",encoding="utf-8") as f:
            json.dump({k:getattr(core.Config,k) for k in resolved.keys()},f,indent=2)
        print("Saved:",args.dump_config)
    core.main()
if __name__=="__main__":
    main()
