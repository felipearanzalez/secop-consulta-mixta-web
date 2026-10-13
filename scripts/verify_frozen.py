"""Verificacion reproducible de los componentes congelados respecto a 2.10."""
from pathlib import Path
import hashlib
import subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE="364acf769ee42024a876a061164708245eda57e4"
FILES=("app.js","index.html","styles.css","croma_backend.py","index27/api.py",
       "index27/store.py","index27/verified_cases.json","index27/worker.py","render.yaml")


def main():
    for name in FILES:
        original=subprocess.run(["git","show",BASE+":"+name],cwd=ROOT,capture_output=True,check=True).stdout
        current=(ROOT/name).read_bytes()
        if original!=current:
            raise SystemExit("Cambios en componente congelado: "+name)
        print(name,hashlib.sha256(current).hexdigest(),"identico_2.10")


if __name__=="__main__":
    main()
