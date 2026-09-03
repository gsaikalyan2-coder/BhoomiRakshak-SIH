"""BhoomiRakshak — Phase 1 exit-criterion verification.

Runs every Phase 1 exit check against whatever DATABASE_URL points at — the local
docker container or the shared Supabase project — and prints one PASS/FAIL line per
check. Exits 0 only if every check passes.

    python scripts/verify_phase1.py

Preferred over scripts/verify_phase1.sql on Windows, where `psql` is usually not on
PATH. It uses only SQLAlchemy + psycopg, which backend/requirements.txt already pins.

Tolerates the two ways PostGIS gets installed: into `public` (local container, created
by migration 0001) or into `extensions` (Supabase convention).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

EXPECTED_ROWS = {
    "admin_units": 768,
    "officers": 41,
    "projects": 900,
    "risk_history": 4500,
    "status_log": 4518,
    "succession_claims": 927,
    "succession_risk": 362,
    "project_dependencies": 628,
}

EXPECTED_STATISTICS = {
    "states": 8,
    "districts": 32,
    "tehsildars": 128,
    "villages": 768,
    "ri_circles": 256,
    "plots": 2293187,
    "khatiyans": 1612419,
    "tenants": 573899,
}

HEAD_REVISION = "0003"

results: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def check_connection(conn: Connection) -> None:
    row = conn.execute(
        text(
            "SELECT current_setting('server_version') AS pg, "
            "postgis_lib_version() AS postgis, current_database() AS db"
        )
    ).one()
    record(
        "PostGIS available",
        True,
        f"PostgreSQL {row.pg}, PostGIS {row.postgis}, database '{row.db}'",
    )


def check_migrations(conn: Connection) -> None:
    exists = conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
    if not exists:
        record(
            "alembic upgrade head applied",
            False,
            "no alembic_version table — run `alembic upgrade head`",
        )
        return
    revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    record(
        "alembic upgrade head applied",
        revision == HEAD_REVISION,
        f"at revision {revision} (expected {HEAD_REVISION})",
    )


def check_row_counts(conn: Connection) -> None:
    for table, expected in EXPECTED_ROWS.items():
        actual = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        record(f"{table} row count", actual == expected, f"{actual} rows (expected {expected})")


def check_geometry(conn: Connection) -> None:
    sample = conn.execute(text("""
            SELECT p.ulpin, p.district, ST_AsText(p.geom) AS wkt,
                   ST_Within(p.geom, d.geom) AS inside
            FROM projects p
            JOIN district_boundaries d ON d.state = p.state AND d.district = p.district
            LIMIT 1
            """)).one()
    record(
        "ST_AsText(geom) returns a point inside its own district",
        bool(sample.inside),
        f"{sample.ulpin} ({sample.district}) -> {sample.wkt}",
    )

    offenders = conn.execute(text("""
            SELECT count(*) FROM projects p
            JOIN district_boundaries d ON d.state = p.state AND d.district = p.district
            WHERE NOT ST_Within(p.geom, d.geom)
            """)).scalar_one()
    record("every project pin inside its district", offenders == 0, f"{offenders} offenders")


def check_statistics(conn: Connection) -> None:
    row = conn.execute(text("""
            SELECT count(DISTINCT state) AS states,
                   count(DISTINCT (state, district)) AS districts,
                   count(DISTINCT tehsildar) AS tehsildars,
                   count(DISTINCT (state, district, taluk, village)) AS villages,
                   count(DISTINCT ri_circle) AS ri_circles,
                   sum(no_plots) AS plots,
                   sum(no_khatiyans) AS khatiyans,
                   sum(no_tenants) AS tenants
            FROM admin_units
            """)).one()
    actual = {k: int(getattr(row, k)) for k in EXPECTED_STATISTICS}
    mismatches = {k: (actual[k], v) for k, v in EXPECTED_STATISTICS.items() if actual[k] != v}
    record(
        "state statistics panel",
        not mismatches,
        f"{actual['states']} states / {actual['districts']} districts / "
        f"{actual['tehsildars']} tehsildars / {actual['villages']} villages / "
        f"{actual['ri_circles']} RI circles / {actual['plots']:,} plots / "
        f"{actual['khatiyans']:,} khatiyans / {actual['tenants']:,} tenants"
        + (f" — mismatches: {mismatches}" if mismatches else ""),
    )


def check_passwords(conn: Connection) -> None:
    row = conn.execute(text("""
            SELECT count(*) FILTER (WHERE password_hash LIKE '$2%') AS bcrypt,
                   count(*) FILTER (WHERE password_hash ~ '^[0-9a-f]{64}$') AS sha256,
                   count(*) AS total
            FROM officers
            """)).one()
    record(
        "every officer carries a bcrypt hash, no SHA-256 survives",
        row.bcrypt == row.total and row.sha256 == 0,
        f"{row.bcrypt}/{row.total} bcrypt, {row.sha256} SHA-256",
    )


def check_issue_resolutions(conn: Connection) -> None:
    cleared = conn.execute(text("""
            SELECT count(*) FROM issue_resolutions r
            JOIN projects p USING (ulpin)
            WHERE p.is_closed_project AND r.cleared_on IS NOT NULL
            """)).scalar_one()
    record(
        "issue_resolutions returns cleared dates for closed projects",
        cleared > 0,
        f"{cleared} dated clearances",
    )


def check_indexes(conn: Connection) -> None:
    # Scoped to `public` deliberately. Supabase ships its own schemas — auth, storage,
    # realtime, vault — and several of their tables carry unindexed foreign keys
    # (auth.mfa_challenges, auth.oauth_authorizations, storage.s3_multipart_uploads_parts
    # and others). Those are Supabase's to fix, not ours, and counting them made this
    # check report 7 failures against a schema that was in fact clean.
    row = conn.execute(text("""
            SELECT count(*) AS total,
                   count(*) FILTER (
                       WHERE NOT EXISTS (
                           SELECT 1 FROM pg_index i
                           WHERE i.indrelid = c.conrelid
                             AND (i.indkey::int2[])[0:array_length(c.conkey, 1) - 1] = c.conkey
                       )
                   ) AS unindexed
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE c.contype = 'f' AND n.nspname = 'public'
            """)).one()
    record(
        "every foreign key has an index",
        row.unindexed == 0 and row.total > 0,
        f"{row.unindexed} unindexed of {row.total} foreign keys in schema public",
    )

    gist = conn.execute(text("""
            SELECT count(*) FROM pg_index i
            JOIN pg_class c ON c.oid = i.indexrelid
            JOIN pg_am am ON am.oid = c.relam
            JOIN pg_class t ON t.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE am.amname = 'gist' AND n.nspname = 'public'
            """)).scalar_one()
    record(
        "every geometry column has a GiST index, no duplicates",
        gist == 3,
        f"{gist} GiST indexes (expected exactly 3)",
    )


def guarded(label: str, fn, conn: Connection) -> None:
    """Run one check group; turn any database error into a FAIL line, never a stack trace.

    A database that has not had `alembic upgrade head` run against it fails almost every
    query here, and an operator staring at a psycopg traceback learns nothing useful.
    """
    try:
        fn(conn)
    except Exception as exc:  # noqa: BLE001 — a failed check is a result, not a crash
        message = str(exc).split("\n")[0]
        record(label, False, message)
        conn.rollback()


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is not set — fill .env from .env.example first.")
        return 1

    host = urlparse(database_url.replace("postgresql+psycopg", "postgresql")).hostname or "?"
    target = "Supabase" if "supabase" in host else "local"
    print(f"BhoomiRakshak — Phase 1 verification\nTarget: {target} ({host})\n")

    try:
        engine = create_engine(database_url, future=True)
        connection = engine.connect()
    except Exception as exc:  # noqa: BLE001
        print(f"  [FAIL] could not connect — {str(exc).splitlines()[0]}")
        print(
            "\nPHASE 1 NOT VERIFIED.\n"
            "Check DATABASE_URL in .env. For Supabase use the SESSION POOLER string "
            "(port 5432, host *.pooler.supabase.com), not the direct connection "
            "(IPv6-only) and not the transaction pooler (port 6543)."
        )
        return 1

    with connection as conn:
        guarded("PostGIS available", check_connection, conn)
        guarded("alembic upgrade head applied", check_migrations, conn)
        migrated = any(name == "alembic upgrade head applied" and ok for name, ok, _ in results)
        if not migrated:
            print(
                "\n  Skipping data checks — the schema is not present.\n"
                "  Run:  alembic upgrade head  &&  python scripts/seed.py"
            )
        else:
            guarded("row counts", check_row_counts, conn)
            guarded("geometry", check_geometry, conn)
            guarded("state statistics panel", check_statistics, conn)
            guarded("password hashing", check_passwords, conn)
            guarded("issue_resolutions view", check_issue_resolutions, conn)
            guarded("indexes", check_indexes, conn)

    failed = [name for name, passed, _ in results if not passed]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    if failed:
        print("PHASE 1 NOT VERIFIED. Failed checks:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("PHASE 1 VERIFIED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
