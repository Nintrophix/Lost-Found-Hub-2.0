import sqlite3
from contextlib import closing

from app.db.backup import copy_database


def test_backup_produces_consistent_copy(tmp_path):
    source, destination = tmp_path / "src.db", tmp_path / "out" / "copy.db"
    with closing(sqlite3.connect(source)) as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")
        conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)])
        conn.commit()

    copy_database(source, destination)

    with closing(sqlite3.connect(destination)) as conn:
        assert conn.execute("SELECT count(*) FROM t").fetchone()[0] == 2
