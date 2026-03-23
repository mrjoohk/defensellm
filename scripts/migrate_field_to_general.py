"""Migration script: set all existing field values to 'general'.

Updates:
  - SQLite DB: documents.field, platforms.field
  - RAG index: meta.json doc_field per chunk

Usage:
    python scripts/migrate_field_to_general.py
    python scripts/migrate_field_to_general.py --db data/defense.db --index data/index
"""
import argparse
import json
import pathlib
import sqlite3
import sys


def migrate_db(db_path: pathlib.Path) -> None:
    if not db_path.exists():
        print(f"[SKIP] DB not found: {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()

        cur.execute("UPDATE documents SET field = 'general' WHERE field != 'general'")
        doc_rows = cur.rowcount
        print(f"[DB] documents updated: {doc_rows} rows")

        cur.execute("UPDATE platforms SET field = 'general' WHERE field != 'general'")
        plat_rows = cur.rowcount
        print(f"[DB] platforms updated: {plat_rows} rows")

        conn.commit()
    finally:
        conn.close()


def migrate_index(index_dir: pathlib.Path) -> None:
    meta_path = index_dir / "meta.json"
    if not meta_path.exists():
        print(f"[SKIP] meta.json not found: {meta_path}")
        return

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    updated = 0
    for key, value in meta.items():
        if isinstance(value, dict) and "doc_field" in value:
            if value["doc_field"] != "general":
                value["doc_field"] = "general"
                updated += 1

    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INDEX] meta.json chunks updated: {updated}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate field values to 'general'")
    parser.add_argument("--db", default="data/defense.db", help="SQLite DB path")
    parser.add_argument("--index", default="data/index", help="RAG index directory")
    args = parser.parse_args()

    project_root = pathlib.Path(__file__).parent.parent
    db_path = pathlib.Path(args.db) if pathlib.Path(args.db).is_absolute() else project_root / args.db
    index_dir = pathlib.Path(args.index) if pathlib.Path(args.index).is_absolute() else project_root / args.index

    print(f"DB path  : {db_path}")
    print(f"Index dir: {index_dir}")
    print()

    migrate_db(db_path)
    migrate_index(index_dir)

    print()
    print("Migration complete.")


if __name__ == "__main__":
    main()
