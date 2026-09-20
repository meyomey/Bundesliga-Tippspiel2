"""verifiziert das 04_GitHub_Upload-Paket VOR dem Upload (Doku-Block 16).

Simuliert den Stand von GitHub main NACH dem Push: frischer Shallow-Klon
des echten Repos, das aktuelle 04-Zip wird darueber gepackt, dann laufen
die gleichen Checks wie der Actions-Workflow "Tests & Lint":

  1. harter flake8-Gate (E9, F63, F7, F82)
  2. volle pytest-Suite (identisch zum CI-Tests-Step)

Aufruf aus dem Repo-Root:
    python verify_04.py

Exit 0 = Paket ist CI-faehig (Upload loesen), != 0 = NICHT hochladen.
Die Skript-Datei selbst ist nur in Paket 02 enthalten und nie auf dem
Netcup-Server.
"""
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_URL = "https://github.com/meyomey/Bundesliga-Tippspiel2.git"


def latest_04_zip() -> Path:
    zips = sorted((ROOT / "_lieferungen").glob("04_GitHub_Upload_*.zip"))
    if not zips:
        sys.exit("FEHLER: kein 04_GitHub_Upload_*.zip in _lieferungen/ – zuerst `python build_lieferungen.py` bauen.")
    return zips[-1]


def project_venv() -> Path:
    """Projekt-Venv wiederverwenden (gleiche requirements), sonst neu anlegen."""
    venv = ROOT / ".venv"
    if not (venv / "bin" / "python").exists():
        venv = Path(tempfile.mkdtemp(prefix="verify04_venv_")) / "venv"
        print(f"--> keine Projekt-.venv gefunden, anlege {venv}")
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    return venv


def main() -> int:
    zip_path = latest_04_zip()
    print(f"== verify_04: {zip_path.name} ==\n")

    venv = project_venv()
    py = str(venv / "bin" / "python")

    work = Path(tempfile.mkdtemp(prefix="verify04_"))
    clone = work / "repo"
    try:
        print(f"--> frischer Klon von {REPO_URL}")
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(clone)],
                       check=True, capture_output=True)
        head = subprocess.run(["git", "-C", str(clone), "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        print(f"    Klon-HEAD: {head}")

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            zf.extractall(clone)
        print(f"    04-Zip uebergelegt: {len(names)} Eintraege")

        print("--> Abhaengigkeiten installieren (requirements.txt + Test-Tools)")
        # Sandbox-Praxis (Uebergabe-Doku): psycopg2-binary wird herausgefiltert –
        # PostgreSQL-only, die Tests laufen auf SQLite. Auf der echten CI wird
        # requirements.txt ohne Filter installiert (dort ist es lauffaehig).
        req_lines = (clone / "requirements.txt").read_text().splitlines()
        filtered = [l for l in req_lines if not l.startswith("psycopg2-binary")]
        (clone / "requirements_nopsq.txt").write_text("\n".join(filtered) + "\n")
        subprocess.run([py, "-m", "pip", "install", "--quiet", "-r", "requirements_nopsq.txt"],
                       cwd=clone, check=True)
        subprocess.run([py, "-m", "pip", "install", "--quiet", "flake8", "pytest", "pytest-cov"],
                       cwd=clone, check=True)

        print("--> harter flake8-Gate (wie CI-Lint-Job)")
        gate = subprocess.run([py, "-m", "flake8", ".",
                               "--exclude=.venv,htmlcov,__pycache__,.pytest_cache",
                               "--count", "--select=E9,F63,F7,F82", "--show-source", "--statistics"],
                              cwd=clone, capture_output=True, text=True)
        sys.stdout.write(gate.stdout)
        if gate.returncode != 0:
            sys.stderr.write(gate.stderr)
            print("\nFEHLER: flake8-Gate rot – 04-Paket NICHT hochladen.")
            return 1

        print("--> volle Testsuite (wie CI-Test-Job: python -m pytest -q)")
        suite = subprocess.run([py, "-m", "pytest", "-q"], cwd=clone, capture_output=True, text=True)
        tail = "\n".join(suite.stdout.splitlines()[-6:])
        print(tail)
        if suite.returncode != 0:
            print("\nFEHLER: Testsuite rot – 04-Paket NICHT hochladen.")
            return 1

        print("\nOK: 04-Paket deckt GitHub main korrekt ab, Gate + Suite gruen. Upload loesen.")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
