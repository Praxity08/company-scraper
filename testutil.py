"""Test helper: a throw-away Neon schema named test_<random>. Only that schema is ever dropped."""
import secrets

import db
import settings


def create_schema(conn):
    name = "test_" + secrets.token_hex(4)
    conn.execute(f'CREATE SCHEMA "{name}"')
    try:
        text = "\n".join(line for line in open(settings.ROOT / "schema.sql", encoding="utf-8").read().splitlines()
                         if not line.strip().startswith("--"))
        with conn.transaction():
            conn.execute(f'SET LOCAL search_path TO "{name}"')
            for statement in (s for s in text.split(";") if s.strip()):
                conn.execute(statement)
    except Exception:
        drop_schema(conn, name)
        raise
    return name


def drop_schema(conn, name):
    assert name.startswith("test_"), "refusing to drop a schema that is not a test schema"
    conn.execute(f'DROP SCHEMA "{name}" CASCADE')


class SchemaMixin:
    """setUpClass/tearDownClass that point db.SCHEMA at a fresh throw-away schema."""

    @classmethod
    def setUpClass(cls):
        cls.db = db
        cls.conn = db.connect()
        cls.schema = create_schema(cls.conn)
        cls.old_schema, db.SCHEMA = db.SCHEMA, cls.schema

    @classmethod
    def tearDownClass(cls):
        db.SCHEMA = cls.old_schema
        drop_schema(cls.conn, cls.schema)
        cls.conn.close()
