"""Consistent SQLite backup and restore using the sqlite3 online backup API.

Usage:
    python -m app.db.backup backup [destination.db]
    python -m app.db.backup restore <source.db>

Restore overwrites the configured database. Stop the API server before restoring.
"""

import argparse
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import make_url

from app.core.config import BACKEND_DIR, get_settings


def database_path() -> Path:
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise SystemExit("Backup/restore requires a file-based SQLite DATABASE_URL.")
    return Path(url.database)


def copy_database(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise SystemExit(f"Source database not found: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)
        result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"Integrity check failed on {destination}: {result}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    backup_cmd = sub.add_parser("backup")
    backup_cmd.add_argument("destination", nargs="?", type=Path)
    restore_cmd = sub.add_parser("restore")
    restore_cmd.add_argument("source", type=Path)
    args = parser.parse_args()

    db_path = database_path()
    if args.command == "backup":
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        destination = args.destination or BACKEND_DIR / "backups" / f"lostfound-{stamp}.db"
        copy_database(db_path, destination)
        print(f"Backup written to {destination}")
    else:
        copy_database(args.source, db_path)
        print(f"Database restored from {args.source}")


if __name__ == "__main__":
    main()
