"""SQLite layer. DDL is generated from ept.schema; writes are idempotent upserts."""

from __future__ import annotations

import json
import sqlite3
import types
import typing
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from pydantic import BaseModel

from ept.config import get_config
from ept.schema import TABLES, TableSpec, _Row, table_for


def connect(path: Optional[Path] = None) -> sqlite3.Connection:
    path = Path(path) if path else get_config().path("db")
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _unwrap(annotation: Any) -> tuple[Any, bool]:
    """Return (inner type, nullable) for Optional[X] / X | None."""
    origin = typing.get_origin(annotation)
    if origin in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return args[0], len(args) < len(typing.get_args(annotation))
    return annotation, False


def _is_json(annotation: Any) -> bool:
    inner, _ = _unwrap(annotation)
    return typing.get_origin(inner) in (list, dict) or inner in (list, dict)


def _sql_type(annotation: Any) -> str:
    inner, _ = _unwrap(annotation)
    if _is_json(annotation):
        return "TEXT"
    if inner is bool or inner is int:
        return "INTEGER"
    if inner is float:
        return "REAL"
    return "TEXT"


def _nullable(table: TableSpec, name: str) -> bool:
    field = table.model.model_fields[name]
    return _unwrap(field.annotation)[1]


def _simple_pk(table: TableSpec) -> bool:
    return not any(_nullable(table, c) for c in table.pk)


def ddl(table: TableSpec) -> list[str]:
    cols = []
    for name, field in table.model.model_fields.items():
        col = f"{name} {_sql_type(field.annotation)}"
        if not _nullable(table, name):
            col += " NOT NULL"
        cols.append(col)
    if _simple_pk(table):
        cols.append(f"PRIMARY KEY ({', '.join(table.pk)})")
    for col, ref in table.fks.items():
        cols.append(f"FOREIGN KEY ({col}) REFERENCES {ref}")
    stmts = [f"CREATE TABLE IF NOT EXISTS {table.name} (\n  " + ",\n  ".join(cols) + "\n)"]
    if not _simple_pk(table):
        keys = ", ".join(f"ifnull({c}, '')" if _nullable(table, c) else c for c in table.pk)
        stmts.append(f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{table.name}_pk ON {table.name} ({keys})")
    if "doc_id" in table.model.model_fields and table.name == "chunks":
        stmts.append("CREATE INDEX IF NOT EXISTS ix_chunks_doc ON chunks (doc_id)")
    return stmts


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables; safe to re-run. Raises if an existing table's columns differ from schema.py."""
    for table in TABLES.values():
        for stmt in ddl(table):
            conn.execute(stmt)
        existing = [r["name"] for r in conn.execute(f"PRAGMA table_info({table.name})")]
        expected = list(table.model.model_fields)
        if existing != expected:
            raise RuntimeError(f"table {table.name} columns {existing} differ from schema.py {expected}")
    conn.commit()


def _to_row(model: _Row) -> dict[str, Any]:
    data = model.model_dump(mode="json")
    for name, field in type(model).model_fields.items():
        if _is_json(field.annotation) and data[name] is not None:
            data[name] = json.dumps(data[name], ensure_ascii=False)
    return data


def _from_row(table: TableSpec, row: sqlite3.Row) -> _Row:
    data = dict(row)
    for name, field in table.model.model_fields.items():
        if _is_json(field.annotation) and data.get(name) is not None:
            data[name] = json.loads(data[name])
    return table.model.model_validate(data)


def upsert(conn: sqlite3.Connection, model: _Row, commit: bool = True) -> None:
    table = table_for(type(model))
    data = _to_row(model)
    cols = list(data)
    placeholders = ", ".join("?" for _ in cols)
    if _simple_pk(table):
        updates = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in table.pk)
        sql = (
            f"INSERT INTO {table.name} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT ({', '.join(table.pk)}) DO UPDATE SET {updates}"
        )
        conn.execute(sql, [data[c] for c in cols])
    else:
        where = " AND ".join(f"{c} IS ?" for c in table.pk)
        conn.execute(f"DELETE FROM {table.name} WHERE {where}", [data[c] for c in table.pk])
        conn.execute(
            f"INSERT INTO {table.name} ({', '.join(cols)}) VALUES ({placeholders})", [data[c] for c in cols]
        )
    if commit:
        conn.commit()


def upsert_many(conn: sqlite3.Connection, models: Iterable[_Row]) -> int:
    n = 0
    with conn:
        for m in models:
            upsert(conn, m, commit=False)
            n += 1
    return n


def get(conn: sqlite3.Connection, table: str, pk: Any) -> Optional[_Row]:
    spec = TABLES[table]
    values = pk if isinstance(pk, (tuple, list)) else (pk,)
    if len(values) != len(spec.pk):
        raise ValueError(f"{table} primary key is {spec.pk}")
    values = [v.isoformat() if hasattr(v, "isoformat") else v for v in values]
    where = " AND ".join(f"{c} IS ?" for c in spec.pk)
    row = conn.execute(f"SELECT * FROM {table} WHERE {where}", values).fetchone()
    return _from_row(spec, row) if row else None


def query(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> list[sqlite3.Row]:
    return conn.execute(sql, params).fetchall()


def select_models(conn: sqlite3.Connection, table: str, where: str = "", params: Sequence[Any] = ()) -> list[_Row]:
    spec = TABLES[table]
    sql = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
    return [_from_row(spec, r) for r in conn.execute(sql, params)]


def as_model(table: str, row: sqlite3.Row) -> BaseModel:
    return _from_row(TABLES[table], row)


def sync_terms(conn: sqlite3.Connection) -> int:
    """Load the terms table from config."""
    return upsert_many(conn, get_config().settings.terms)
