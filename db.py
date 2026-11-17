"""Neon (Postgres) storage for scrapes, Hunter contacts and daily counters.

Every table name is written with its schema (e.g. public.scrapes), so it also works through
Neon's connection pooler. Tests set SCHEMA to a throw-away "test_..." schema.
Error messages from here are never shown on the page (only the error type is).
"""
import uuid

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import settings

SCHEMA = "public"
IST_TODAY = sql.SQL("(now() AT TIME ZONE 'Asia/Kolkata')::date")


class NotConfigured(Exception):
    pass


def configured():
    return bool(settings.database_url())


def connect():
    url = settings.database_url()
    if not url:
        raise NotConfigured("DATABASE_URL is not set")
    return psycopg.connect(url, autocommit=True, connect_timeout=10,
                           prepare_threshold=None, row_factory=dict_row)


def t(name):
    return sql.Identifier(SCHEMA, name)


def as_uuid(value):
    """A UUID object, or None if the text is not a valid id."""
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------- scrapes

def save_scrape(conn, result, test_only=False):
    row = conn.execute(
        sql.SQL("INSERT INTO {} (domain, status, found, missing, result, test_only) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, created_at").format(t("scrapes")),
        (result["domain"], result["status"], list(result.get("found", [])),
         list(result.get("missing", [])), Jsonb(result), bool(test_only)),
    ).fetchone()
    return str(row["id"]), row["created_at"]


def list_scrapes(conn, limit):
    """Newest scrapes, without page text or contact details."""
    rows = conn.execute(
        sql.SQL("SELECT s.id, s.created_at, s.domain, s.status, s.found, s.missing, s.test_only, c.outcome, "
                "k.decision, (k.email IS NOT NULL) AS drafted, k.sent_at "
                "FROM {} s LEFT JOIN {} c ON c.scrape_id = s.id LEFT JOIN {} k ON k.scrape_id = s.id "
                "ORDER BY s.created_at DESC LIMIT %s").format(t("scrapes"), t("contacts"), t("campaign")),
        (limit,),
    ).fetchall()
    return [{"id": str(r["id"]), "created_at": r["created_at"].isoformat(), "domain": r["domain"],
             "status": r["status"], "found": r["found"], "missing": r["missing"],
             "test_only": r["test_only"], "contact": r["outcome"], "decision": r["decision"],
             "drafted": r["drafted"], "sent": r["sent_at"] is not None} for r in rows]


def get_scrape(conn, scrape_id):
    sid = as_uuid(scrape_id)
    if sid is None:
        return None
    row = conn.execute(
        sql.SQL("SELECT id, created_at, result, test_only FROM {} WHERE id = %s").format(t("scrapes")), (sid,)
    ).fetchone()
    if not row:
        return None
    result = dict(row["result"])
    result["scrape_id"] = str(row["id"])
    result["saved_at"] = row["created_at"].isoformat()
    result["test_only"] = row["test_only"]
    return result


# ---------------------------------------------------------------- contacts

def purge_old_contacts(conn, keep_days):
    """Delete contacts older than keep_days, and lookups stuck as 'pending' for 10+ minutes."""
    conn.execute(
        sql.SQL("DELETE FROM {} WHERE (outcome <> 'pending' AND created_at < now() - make_interval(days => %s)) "
                "OR (outcome = 'pending' AND created_at < now() - interval '10 minutes')").format(t("contacts")),
        (keep_days,),
    )


def get_contact(conn, scrape_id):
    sid = as_uuid(scrape_id)
    if sid is None:
        return None
    row = conn.execute(
        sql.SQL("SELECT outcome, contact, created_at FROM {} WHERE scrape_id = %s").format(t("contacts")), (sid,)
    ).fetchone()
    if not row:
        return None
    return {"outcome": row["outcome"], "contact": row["contact"], "looked_up_at": row["created_at"].isoformat()}


def claim_contact(conn, scrape_id, domain):
    """Mark a lookup as started. False if this scrape already has (or is getting) one."""
    row = conn.execute(
        sql.SQL("INSERT INTO {} (scrape_id, domain, outcome) VALUES (%s, %s, 'pending') "
                "ON CONFLICT (scrape_id) DO NOTHING RETURNING scrape_id").format(t("contacts")),
        (as_uuid(scrape_id), domain),
    ).fetchone()
    return row is not None


def finish_contact(conn, scrape_id, outcome, contact):
    conn.execute(
        sql.SQL("UPDATE {} SET outcome = %s, contact = %s, created_at = now() "
                "WHERE scrape_id = %s").format(t("contacts")),
        (outcome, Jsonb(contact) if contact is not None else None, as_uuid(scrape_id)),
    )


def release_contact(conn, scrape_id):
    """Undo a claim after a failed lookup, so it can be tried again."""
    conn.execute(
        sql.SQL("DELETE FROM {} WHERE scrape_id = %s AND outcome = 'pending'").format(t("contacts")),
        (as_uuid(scrape_id),),
    )


# ---------------------------------------------------------------- daily counters

def reserve(conn, name, cap):
    """Add 1 to today's counter if it is below cap. False if the cap is reached."""
    row = conn.execute(
        sql.SQL("INSERT INTO {t} AS c (day, name, n) VALUES ({today}, %s, 1) "
                "ON CONFLICT (day, name) DO UPDATE SET n = c.n + 1 WHERE c.n < %s "
                "RETURNING n").format(t=t("counters"), today=IST_TODAY),
        (name, cap),
    ).fetchone()
    return row is not None


def release(conn, name):
    """Give back one unit (used when Hunter could not be reached)."""
    conn.execute(
        sql.SQL("UPDATE {} SET n = greatest(n - 1, 0) WHERE day = {} AND name = %s").format(
            t("counters"), IST_TODAY),
        (name,),
    )


def count(conn, name):
    row = conn.execute(
        sql.SQL("SELECT n FROM {} WHERE day = {} AND name = %s").format(t("counters"), IST_TODAY), (name,)
    ).fetchone()
    return row["n"] if row else 0


# ---------------------------------------------------------------- campaign record

CAMPAIGN_FIELDS = {"picture", "checks", "decision", "flag_approved", "pain", "email"}
JSON_FIELDS = {"picture", "checks", "pain", "email"}


def get_campaign(conn, scrape_id):
    """The campaign record for a scrape, or None. Dates are ISO strings."""
    sid = as_uuid(scrape_id)
    if sid is None:
        return None
    row = conn.execute(sql.SQL("SELECT * FROM {} WHERE scrape_id = %s").format(t("campaign")), (sid,)).fetchone()
    if not row:
        return None
    out = dict(row)
    out["scrape_id"] = str(out["scrape_id"])
    for k in ("updated_at", "sent_at"):
        out[k] = out[k].isoformat() if out[k] else None
    return out


def update_campaign(conn, scrape_id, domain, **fields):
    """Create the record if needed, then set the given fields (only known columns)."""
    bad = set(fields) - CAMPAIGN_FIELDS
    if bad:
        raise ValueError(f"unknown campaign fields: {sorted(bad)}")
    cols = list(fields)
    vals = [Jsonb(fields[c]) if c in JSON_FIELDS and fields[c] is not None else fields[c] for c in cols]
    insert_cols = sql.SQL(", ").join(sql.Identifier(c) for c in ["scrape_id", "domain"] + cols)
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in range(2 + len(cols)))
    updates = sql.SQL(", ").join(
        [sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(c), sql.Identifier(c)) for c in cols]
        + [sql.SQL("updated_at = now()")])
    conn.execute(
        sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT (scrape_id) DO UPDATE SET {}").format(
            t("campaign"), insert_cols, placeholders, updates),
        [as_uuid(scrape_id), domain] + vals,
    )


def mark_sent(conn, scrape_id):
    """Set sent_at once. False if it was already sent (never twice)."""
    row = conn.execute(
        sql.SQL("UPDATE {} SET sent_at = now(), updated_at = now() "
                "WHERE scrape_id = %s AND sent_at IS NULL RETURNING scrape_id").format(t("campaign")),
        (as_uuid(scrape_id),),
    ).fetchone()
    return row is not None


def save_send_result(conn, scrape_id, result):
    conn.execute(sql.SQL("UPDATE {} SET send_result = %s WHERE scrape_id = %s").format(t("campaign")),
                 (Jsonb(result), as_uuid(scrape_id)))


def unmark_sent(conn, scrape_id):
    """Only after Resend clearly refused the email (nothing was sent)."""
    conn.execute(sql.SQL("UPDATE {} SET sent_at = NULL WHERE scrape_id = %s").format(t("campaign")),
                 (as_uuid(scrape_id),))
