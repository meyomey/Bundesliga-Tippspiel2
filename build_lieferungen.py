#!/usr/bin/env python3
"""Build-Skript fuer die Lieferpakete der Wulmstoerper Tipprunde.

Erzeugt aus dem aktuellen Repo-Stand unter _lieferungen/:
  01_Runtime_YYYY-MM-DD.zip     -> alles, was in den Netcup Application Root muss
  02_Doku_Tests_YYYY-MM-DD.zip  -> Doku, Tests, Dev-Werkzeuge
  03_Deploy_YYYY-MM-DD.zip      -> kompletter Runtime-Stand + DEPLOY_ANLEITUNG.txt
                                  (Upload-Checkliste, Nicht-Ueberschreiben-Hinweise,
                                  Verifikation nach Restart)
  04_GitHub_Upload_YYYY-MM-DD.zip -> die Dateien, die auf GitHub fehlen/geaendert
                                  sind (fuer GitHub Desktop, inkl. Anleitung)

Aufruf: python build_lieferungen.py   (aus dem Repo-Root)
"""
import subprocess
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIEF = ROOT / "_lieferungen"
TODAY = date.today().isoformat()

# ---------------------------------------------------------------- Auswahl --
DEV_PY = {"generate_pwa_icons.py", "scheduler.py"}          # Dev-/Standalone-Skripte
BROKEN_AVATARS = set()  # veraltet: kaputte Avatar-Stubs wurden aus dem Repo entfernt
NOT_RUNTIME = DEV_PY | {"build_lieferungen.py"}              # nur in 02, nicht auf den Server

# Dateien, die auf GitHub fehlen bzw. seit dem letzten Stand geaendert sind
# (fuer 04_GitHub_Upload). Nach dem GitHub-Push (Commit 445dcf2) kamen lokal
# dazu: Coverage-Suite, CHANGELOG-Eintrag, build_lieferungen.py v2 (04-Skip).
# Nach dem naechsten Push wieder leeren.
# Nach dem Push (31.08. abends) geleert: 04_GitHub_Upload entfaellt automatisch,
# solange keine offenen GitHub-Aenderungen existieren. Beim naechsten lokalen
# Aenderungsblock einfach wieder befuellen.
GITHUB_UPLOAD_FILES = [
    # 01.09.2026: Python 3.9 als feste Netcup-Rahmenbedingung dokumentiert
    "DEPLOY_NETCUP.md",
    "NETCUP_OHNE_SSH.md",
    "requirements.txt",
    "requirements_py39.txt",
    ".github/workflows/tests.yml",
    # 01.09.2026: Dependabot + pip-audit (Sicherheits-Automatik)
    ".github/dependabot.yml",
    # 01.09.2026: README-Badges/-Teststand aktualisiert (281/281, 79 %)
    "README.md",
    # 01.09.2026: DB-Backup + Cron-Heartbeat (Prio 1 Produktions-Absicherung)
    "cron_jobs.py",
    "cron_heartbeat.py",
    "backup.py",
    "maintenance.py",
    "admin_maintenance_routes.py",
    "routes_admin.py",
    "templates/admin/maintenance.html",
    "tests/test_cron_backup.py",
    # 01.09.2026: HTTP-Cron für Plesk-chroot (kein Python im Cron)
    "main_cron_routes.py",
    "app.py",
    "config.py",
    ".gitignore",
    "CHANGELOG.md",
    "build_lieferungen.py",
]

def tracked_files() -> list:
    # tracked + untracked (aber nicht gitignorte) Dateien:
    # so landen neu angelegte Dateien (z. B. .github/workflows/tests.yml)
    # schon vor ihrem ersten Commit in den Paketen.
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout.splitlines()
    return out

def commit_info() -> tuple:
    h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True, check=True).stdout.strip()
    d = subprocess.run(["git", "log", "-1", "--format=%ad", "--date=format:%Y-%m-%d %H:%M"],
                       cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    return h, d

def collect(paths: list, exclude: set = frozenset()) -> list:
    out = []
    for p in sorted(paths):
        if p in exclude or p.startswith("_lieferungen/"):
            continue
        out.append(p)
    return out

def manifest_01(commit: str, commit_date: str) -> str:
    return f"""WULMSTOERPER TIPPRUNDE - LIEFERPAKET 01 RUNTIME
====================================================
Build-Datum:   {TODAY}
Quelle:        git clone meyomey/Bundesliga-Tippspiel2
Commit:        {commit} ({commit_date})
Teststand:     281/281 Tests gruen, Coverage 79 %
Python-Ziel:   3.9 (Netcup/Plesk), kompatibel bis 3.13

INHALT (ZIP direkt in den Application Root entpacken):
- passenger_wsgi.py  (Pflicht! Entry Point)
- alle Runtime-Python-Module (*.py am Root)
- requirements.txt + requirements_py39.txt
- templates/  (komplett)
- static/     (komplett)

NICHT ENTHALTEN - bitte beachten:
- vendor/ (manylinux-Wheels fuer Python 3.9): lokal per build_vendor.bat
  bauen und separat per FTP hochladen.
- .env: liegt auf dem Server - beim Upload NICHT ueberschreiben!
- tippspiel.db: SQLite-Datenbank auf dem Server NICHT ueberschreiben!
- .htaccess: nicht im Repo, liegt bereits auf dem Server.

NACH DEM UPLOAD: Plesk -> Python -> Restart App.
"""

def manifest_02(commit: str, commit_date: str) -> str:
    return f"""WULMSTOERPER TIPPRUNDE - LIEFERPAKET 02 DOKU + TESTS
====================================================
Build-Datum:   {TODAY}
Quelle:        git clone meyomey/Bundesliga-Tippspiel2
Commit:        {commit} ({commit_date})
Teststand:     281/281 Tests gruen, Coverage 79 %

INHALT:
- Doku:      README.md, CHANGELOG.md, FEATURES.md, OPTIMIZATION_ROADMAP.md,
             ANALYSE_BUNDESLIGA_TIPPSPIEL.md, AUDIT_2026-07-06.md,
             SYNC_AUDIT_2026-07-06.md, DEPLOY_NETCUP.md,
             NETCUP_OHNE_SSH.md, NETCUP_TROUBLESHOOTING.md, docs/
- Tests:     tests/ (31 Dateien, 235 Tests) + pytest.ini
- CI:        .github/workflows/tests.yml (flake8-Gate + pytest-Matrix 3.9-3.13)
- Dev-Tools: build_vendor.bat, install.bat, start.bat, start_scheduler.bat,
             generate_pwa_icons.py, scheduler.py, build_lieferungen.py
- Docker:    Dockerfile, docker-compose.yml
- Repo:      .gitignore (schuetzt vor Datenbank-/Secret-Commits)
"""

def make_zip(name: str, files: list, manifest: str, manifest_name: str = "MANIFEST.txt") -> Path:
    LIEF.mkdir(exist_ok=True)
    dest = LIEF / name
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(manifest_name, manifest)
        for f in files:
            z.write(ROOT / f, arcname=f)
    return dest


def manifest_deploy(commit: str, commit_date: str) -> str:
    return f"""WULMSTOERPER TIPPRUNDE - DEPLOY-PAKET (kompletter Runtime-Stand)
================================================================
Build-Datum:   {TODAY}
Quelle:        git clone meyomey/Bundesliga-Tippspiel2
Commit:        {commit} ({commit_date}) + lokale Aenderungen
Teststand:     281/281 Tests gruen, Coverage 79 %

WAS IST DRIN:
Der KOMPLETTE aktuelle Runtime-Stand: alle Python-Module, templates/,
static/ (inkl. reparierter Team-Logos), requirements.txt +
requirements_py39.txt, passenger_wsgi.py.
Empfohlen, weil seit dem letzten Server-Stand viele zusammenspielende
Aenderungen offen sind (Liste unten).

VOR DEM UPLOAD:
1. Plesk-Backup erstellen (Dateien + ggf. Datenbank sichern).
2. Auf dem Server NICHT ueberschreiben:
   - .env              (Secrets, Mail-Zugang, Token - liegt nur auf dem Server)
   - tippspiel.db      (SQLite-Datenbank! Enthaelt alle echten Daten)
   - .htaccess         (nicht im ZIP enthalten, liegt nur auf dem Server)
   - static/uploads/   (echte Avatare der Mitspieler; Avatar-Dateien sind
                        seit 31.08. aus dem Repo entfernt + gitignored,
                        PWA-Icons werden mitgeliefert)

UPLOAD:
1. ZIP per FTP/Plesk-Filemanager in den Application Root (httpdocs) laden.
2. Entpacken, vorhandene Dateien UEBERSCHREIBEN lassen.
3. Abhaengigkeiten: redis + flask-caching sind seit Langem in
   requirements.txt - falls auf dem Server noch nicht vorhanden, via
   build_vendor.bat (Auswahl [1] Python 3.9.x) + vendor/-FTP nachziehen.

RESTART:
Plesk -> Domain -> Python -> Restart App.

VERIFIKATION NACH RESTART (Browser, ggf. Strg+F5):
- Rangliste: Spaltenkopf heisst "Exaktquote", Legende erklaert sie.
- Seitenkopf: Saisonlabel ohne Jahres-Doppelung ("Bundesliga 2026/27").
- Rangliste/Stats/Tabelle/Sonderfragen: Unterzeile ohne
  "Bundesliga 2026 · Saison 2026" (comp_label-Fix vom 31.08.).
- Team-Logos FCB/BVB/B04/RBL sichtbar (ohne Wartungscenter-Lauf).
- Punkteanzeige stabil (Status-Monotonie-Fix).
- Vorschau/Rueckblick: deutsche Titel + Balkendiagramme (Chart.js).
- Live-Center: Skripte laden aus static/js/ (live.js etc.).

ENTHALTENE AENDERUNGEN (Auswahl, seit ca. 10.08.2026):
- Status-Monotonie-Fix + OLB-Sicherheitsnetz (sync.py, match_results.py)
- Saisonlabel-Fix (competition_helpers.py, app.py, routes_admin.py, 4 Templates)
- Inline-JS/CSS-Auslagerung (6 neue JS + 2 neue CSS in static/)
- Notification-Center-Bulk (notification_center.py)
- Activity-Log-Diffs (audit_log.py, models.py, admin_users_routes.py,
  admin_special_questions_routes.py, templates/admin/activity.html)
- routes_main-Entflechtung (routes_main.py, 6 main_*_routes.py)
- Team-Logos repariert (static/team_logos/)
- Preview/Recap-Redesign + Mini-Charts + deutsche Titel
- Schnelltipp-UX (Buttons ausgrauen, Ergebnis-Chip, S/U/N-Formkurve)
- Mehr-Menue konsistent, Stats-Dashboard-Redesign
- Rangliste: "Quote" -> "Exaktquote" (Header + Legende + Tooltip + Mobil)
- comp_label auf allen Seiten (Rangliste, Tabelle, Stats, Sonderfragen,
  Admin-Dashboard, base-Tooltip); Textmuell in standings.html entfernt
- Repo-Hygiene: .gitignore angelegt, kaputte Avatar-Stubs entfernt,
  Hygiene-Test fuer static/uploads; CI-Workflow liegt im Repo (Paket 02)

ROLLBACK:
Plesk-Backup aus "VOR DEM UPLOAD" zurueckspielen.
"""

def manifest_04(commit: str, commit_date: str) -> str:
    return f"""GITHUB-UPLOAD-PAKET - fuer GitHub Desktop (Stand {TODAY})
====================================================

Dieses Paket enthaelt die Dateien, die auf GitHub fehlen bzw. sich
seit dem letzten Stand geaendert haben. Kopiere den Inhalt in den
lokal geklonten Ordner (Bundesliga-Tippspiel2) und ueberschreibe
vorhandene Dateien.

DANACH in GitHub Desktop:
    1. "Changes" pruefen (12 Dateien: geaendert/neu)
    2. Zusammenfassung schreiben + "Commit to main"
    3. "Push origin"

DIE CI LAEUFT DANN AUTOMATISCH:
    github.com/meyomey/Bundesliga-Tippspiel2 > Actions > "Tests & Lint"
    - Flake8-Gate (Syntaxfehler/undefinierte Namen)
    - pytest auf Python 3.9-3.13 (3.9 = Netcup-Zielversion)

Quelle:  Commit {commit} ({commit_date}) + lokale Aenderungen
Teststand: 281/281 Tests gruen, Coverage 79 %
"""


def main():
    tracked = tracked_files()
    commit, commit_date = commit_info()

    runtime = collect(
        [p for p in tracked
         if p.split("/")[0] not in ("tests", "docs")
         and not p.endswith((".md", ".bat"))
         and p not in ("Dockerfile", "docker-compose.yml", "pytest.ini")
         and (p.endswith((".py", ".txt")) or p.startswith(("templates/", "static/")))],
        exclude=BROKEN_AVATARS | NOT_RUNTIME,
    )
    docs_tests = collect(
        [p for p in tracked
         if p.endswith((".md", ".bat")) or p.startswith(("tests/", "docs/", ".github/"))
         or p in ("pytest.ini", "Dockerfile", "docker-compose.yml", ".gitignore")
         or p in DEV_PY or p == "build_lieferungen.py"],
    )

    z1 = make_zip(f"01_Runtime_{TODAY}.zip", runtime, manifest_01(commit, commit_date))
    z2 = make_zip(f"02_Doku_Tests_{TODAY}.zip", docs_tests, manifest_02(commit, commit_date))
    z3 = make_zip(f"03_Deploy_{TODAY}.zip", runtime, manifest_deploy(commit, commit_date),
                  manifest_name="DEPLOY_ANLEITUNG.txt")

    print(f"01 Runtime : {z1}  ({len(runtime)} Dateien)")
    print(f"02 Doku+Ts : {z2}  ({len(docs_tests)} Dateien)")
    print(f"03 Deploy  : {z3}  ({len(runtime)} Dateien)")
    if GITHUB_UPLOAD_FILES:
        z4 = make_zip(f"04_GitHub_Upload_{TODAY}.zip", GITHUB_UPLOAD_FILES,
                      manifest_04(commit, commit_date),
                      manifest_name="GITHUB_UPLOAD_ANLEITUNG.txt")
        print(f"04 GitHub  : {z4}  ({len(GITHUB_UPLOAD_FILES)} Dateien)")
    else:
        print("04 GitHub  : entfaellt (keine offenen GitHub-Aenderungen)")
    print(f"Commit     : {commit} ({commit_date})")
    unassigned = set(tracked) - set(runtime) - set(docs_tests) - BROKEN_AVATARS - set(GITHUB_UPLOAD_FILES)
    if unassigned:
        print(f"WARNUNG - in keinem Paket: {sorted(unassigned)}")
    duplicated = set(runtime) & set(docs_tests)
    if duplicated:
        print(f"WARNUNG - doppelt zugeordnet (01 UND 02): {sorted(duplicated)}")

if __name__ == "__main__":
    main()
