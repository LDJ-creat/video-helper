from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def main() -> int:
    db_path = Path(r"D:\vh-smoke-data\core.sqlite3")
    out_path = Path(r"D:\video-helper\_bmad-output\implementation-artifacts\jobs-schema.json")
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        cur.execute("PRAGMA table_info(jobs)")
        cols = [{"name": r[1], "type": r[2], "notnull": r[3], "pk": r[5]} for r in cur.fetchall()]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(cols, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(out_path))
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
