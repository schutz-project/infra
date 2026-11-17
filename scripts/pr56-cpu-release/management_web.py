#!/usr/bin/env python3
"""Reconstructed SCHUTZ PR56 release/PR55 rollback workflow.
Run on monitoring EC2 with sudo. Default mode is read-only.
DO NOT run --apply or --rollback outside approved maintenance.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

WEB = "schutz-monitoring-management-web-1"
ROOT = "/opt/schutz-monitoring"
PROJECT = "schutz-monitoring"
IMAGES = {"apply":"schutz-management-web:pr56-release-cpu",
          "rollback":"schutz-management-web:pr55-cpu-policy"}
OVERRIDES = {"apply":f"{ROOT}/compose.pr56-web-only.yaml",
             "rollback":f"{ROOT}/backups/compose.pr55-rollback.yaml"}

def call(args, **kw):
    return subprocess.run(args, check=True, **kw)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    g=p.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="Apply PR56 (modifies production management-web)")
    g.add_argument("--rollback", action="store_true", help="Rollback to PR55 (modifies production management-web)")
    a=p.parse_args()
    info=json.loads(call(["docker","inspect",WEB],capture_output=True,text=True).stdout)[0]
    original_env=dict(s.split("=",1) for s in info["Config"]["Env"] if "=" in s)
    secret=original_env.get("SESSION_CONTROL_SECRET")
    if not secret:
        raise SystemExit("STOP: running web container lacks SESSION_CONTROL_SECRET")
    files=info["Config"]["Labels"]["com.docker.compose.project.config_files"].split(",")
    files=[f for f in files if f not in OVERRIDES.values()]
    if not all(Path(f).is_file() for f in files):
        raise SystemExit("STOP: missing original compose file")
    mode="rollback" if a.rollback else "apply"
    override=OVERRIDES[mode]
    if not Path(override).is_file():
        raise SystemExit(f"STOP: missing override {override}")
    env=os.environ.copy()
    env["SCHUTZ_PHASE2B_PREVIEW_KEY"]=secret
    cmd=["docker","compose","-p",PROJECT]
    for file in [*files,override]:
        cmd.extend(["-f",file])
    cfg=json.loads(call(cmd+["config","--format","json"],cwd=ROOT,env=env,
                        capture_output=True,text=True).stdout)
    actual=cfg["services"]["management-web"]["image"]
    assert actual==IMAGES[mode], "STOP: unexpected image in merged Compose config"
    print("Running:",info["Config"]["Image"])
    print("Target:",actual)
    print("Effective Compose config: valid")
    if not(a.apply or a.rollback):
        print("DRY CHECK ONLY. No containers changed.")
        return
    if a.apply:
        if not any(f.is_file() and f.stat().st_size>0
                   for f in Path(ROOT,"backups").glob("monitor-pr55-*.dump")):
            raise SystemExit("STOP: missing PostgreSQL backup")
    if info["Config"]["Image"]==actual:
        print("Already on requested image.")
        return
    print("Recreating management-web only; brief downtime possible.")
    call(cmd+["up","-d","--no-deps","--no-build","management-web"],cwd=ROOT,env=env)
    updated=json.loads(call(["docker","inspect",WEB],capture_output=True,text=True).stdout)[0]
    print("Image:",updated["Config"]["Image"],"Status:",updated["State"]["Status"])
    if updated["Config"]["Image"]!=actual or updated["State"]["Status"]!="running":
        raise SystemExit("DEPLOYMENT UNHEALTHY: investigate and rollback")
    print("Next: HTTPS /health, login, incident workflow, CPU dashboard chart.")

if __name__=="__main__":
    main()
