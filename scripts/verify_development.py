"""Pruebas reproducibles de desarrollo y conservacion de la version 2.10."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
PATTERNS=("test_documentary_api.py","test_queue_resume.py","test_document_pipeline.py","test_document_ocr.py","test_discovery.py",
          "test_expedientes_incrementales.py","test_secop_i_inventory.py","test_index27.py")


def main():
    args=argparse.ArgumentParser()
    args.add_argument("--output",type=Path)
    opts=args.parse_args()
    suite=unittest.TestSuite()
    for pattern in PATTERNS:
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/"tests"),pattern=pattern))
    tested=unittest.TextTestRunner(verbosity=1).run(suite)
    commands=[[sys.executable,"scripts/verify_frozen.py"],["node","--check","app.js"],
              ["node","tests/test_nit_900317964.js"],["node","tests/test_filter_retry.js"]]
    checks=[]
    for command in commands:
        run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=30)
        checks.append({"command":command,"exit_code":run.returncode,
                       "stdout":run.stdout.strip(),"stderr":run.stderr.strip()})
    result={"checked_at":datetime.now(timezone.utc).isoformat(),"baseline":"364acf769ee42024a876a061164708245eda57e4",
            "unit_tests":tested.testsRun,"failures":len(tested.failures),"errors":len(tested.errors),
            "skipped":[message for _,message in tested.skipped],"checks":checks,
            "passed":tested.wasSuccessful() and all(x["exit_code"]==0 for x in checks)}
    if opts.output:
        opts.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:result[k] for k in ("unit_tests","failures","errors","skipped","passed")},ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
