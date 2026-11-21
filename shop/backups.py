"""
Database backups. Used by `manage.py backup_db`, `manage.py restore_db` and the staff page "Резервные копии".

PostgreSQL -> pg_dump writes a .sql file (the whole database: tables, data, rules).
If pg_dump is not found (or the project runs on SQLite) -> Django writes a .json file with all data.
Files go to the folder backups/ next to manage.py; only the last KEEP files are kept.
"""
import glob
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management import call_command

KEEP = 10
NAME_RE = re.compile(r"^sauda_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.(sql|json)$")
JSON_EXCLUDE = ["contenttypes", "auth.permission", "sessions", "admin.logentry"]

SEARCH_DIRS = [
    "/Library/PostgreSQL/*/bin",                          # EDB installer (Mac, comes with pgAdmin)
    "/Applications/Postgres.app/Contents/Versions/*/bin",  # Postgres.app
    "/opt/homebrew/opt/postgresql@*/bin", "/usr/local/opt/postgresql@*/bin",  # Homebrew
    "/usr/lib/postgresql/*/bin",                          # Linux
    r"C:\Program Files\PostgreSQL\*\bin",                 # Windows
]


def backup_dir() -> Path:
    path = Path(getattr(settings, "BACKUP_DIR", Path(settings.BASE_DIR) / "backups"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_postgres() -> bool:
    return "postgresql" in settings.DATABASES["default"]["ENGINE"]


def _version(path: str) -> tuple:
    nums = re.findall(r"(\d+)", path)
    return tuple(int(n) for n in nums[-2:]) if nums else (0,)


def find_tool(name: str) -> str | None:
    """pg_dump / psql: from PATH, or from the usual install folders (the newest version)."""
    found = shutil.which(name)
    if found:
        return found
    exe = name + (".exe" if os.name == "nt" else "")
    candidates = [p for d in SEARCH_DIRS for p in glob.glob(os.path.join(d, exe))]
    return max(candidates, key=_version) if candidates else None


def _pg_env():
    db = settings.DATABASES["default"]
    env = os.environ.copy()
    env["PGPASSWORD"] = str(db.get("PASSWORD") or "")
    args = ["-h", str(db.get("HOST") or "localhost"), "-p", str(db.get("PORT") or "5432"),
            "-U", str(db.get("USER") or "postgres")]
    return env, args, str(db["NAME"])


def list_backups():
    files = [p for p in backup_dir().iterdir() if p.is_file() and NAME_RE.match(p.name)]
    return sorted(files, key=lambda p: p.name, reverse=True)


def get_backup(name: str) -> Path | None:
    """Only a file from our list (protects from paths like ../../settings.py)."""
    return next((p for p in list_backups() if p.name == name), None)


def _cleanup(keep=KEEP):
    for old in list_backups()[keep:]:
        old.unlink(missing_ok=True)


def create_backup(keep=KEEP, force_json=False) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    pg_dump = find_tool("pg_dump") if is_postgres() and not force_json else None
    if pg_dump:
        target = backup_dir() / f"sauda_{stamp}.sql"
        env, args, name = _pg_env()
        result = subprocess.run(
            [pg_dump, *args, "--clean", "--if-exists", "--no-owner", "--no-privileges", "-f", str(target), name],
            env=env, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            target.unlink(missing_ok=True)
            raise RuntimeError(result.stderr.strip() or "pg_dump failed")
    else:
        target = backup_dir() / f"sauda_{stamp}.json"
        with open(target, "w", encoding="utf-8") as f:
            call_command("dumpdata", exclude=JSON_EXCLUDE, indent=1, stdout=f)
    _cleanup(keep)
    return target


def restore_backup(path: Path):
    if path.suffix == ".json":
        call_command("loaddata", str(path))
        return
    psql = find_tool("psql")
    if not psql:
        raise RuntimeError("psql was not found. Install PostgreSQL command line tools or use a .json backup.")
    env, args, name = _pg_env()
    result = subprocess.run([psql, *args, "-v", "ON_ERROR_STOP=1", "-q", "-d", name, "-f", str(path)],
                            env=env, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "psql failed")
