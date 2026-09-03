# ADR-001 — Supabase as the shared development database

**Date:** 2026-08-23
**Status:** Accepted
**Context of record:** `CLAUDE.md` requires a decision record in `docs/design/` before introducing
a new database. This is not a new database family — it is a second *deployment* of the one already
locked in.

## Decision

Run the BhoomiRakshak schema in **two places**, from the same Alembic migrations:

| Target | Role | Owner |
|---|---|---|
| Local `docker compose up -d db` (postgis/postgis:16-3.4) | **The rehearsed demo path.** What runs on Thursday 2026-08-27. | Each developer, locally |
| Supabase project `bhoomirakshak` (ref `tayflaukyjtcsyuivpxl`, ap-south-1) | Shared development database; the target a deployed backend points at. | Shared, one instance |

The locked decision "Real PostgreSQL 16 + PostGIS 3, not CSV/pandas" is unchanged. Supabase is
where the team shares one seeded database without each person standing up Docker.

## Why not Supabase alone

The demo is the deliverable and it happens once. Pointing it at a hosted database makes it depend
on venue wifi and on the project not having been auto-paused. Free-tier Supabase projects pause
after 7 days idle — 5 of the 6 projects already in this org are paused right now. The local
container has neither failure mode.

## Why not local alone

Two people seeding two databases from the same CSVs diverge the moment either writes a
`risk_scores` or `annotations` row. Phase 3 onward writes state; the shared instance is where that
state agrees.

## Divergences between the two targets, and why each is acceptable

| Item | Local | Supabase | Assessment |
|---|---|---|---|
| PostgreSQL | 16.13 | 17.6 | No migration or query in Phase 1 uses a version-specific feature. Verified on both. |
| PostGIS | 3.4.2 | 3.3.7 | Only `ST_SetSRID`, `ST_MakePoint`, `ST_AsText`, `ST_Within`, `ST_Collect`, `ST_ConvexHull`, `ST_Buffer` are used. All present since PostGIS 2.x. |
| PostGIS schema | `public` | `extensions` | Supabase convention. `search_path` for the `postgres` role is `"$user", public, extensions`, so the unqualified `geometry(POINT,4326)` type in the migrations resolves. Verified on the live project. |
| `pgcrypto` | created by migration `0001` | pre-installed in `extensions` | `CREATE EXTENSION IF NOT EXISTS` no-ops. |

## Consequences and standing rules

1. **Migrations are the only way schema changes reach either target.** Nothing is created by hand
   in the Supabase SQL editor or dashboard. The one exception, already done:
   `create extension if not exists postgis with schema extensions;` — because it must exist before
   `alembic upgrade head` and Supabase installs extensions into `extensions`, not `public`.
2. **Never run `alembic downgrade base` against Supabase.** Migration `0001`'s downgrade drops the
   PostGIS extension. Locally that is a clean reset; on the shared instance it destroys the
   teammate's data and the extension other projects may rely on.
3. **Use the session pooler (port 5432), never the transaction pooler (6543), for Alembic and
   `seed.py`.** Transaction-mode pooling breaks prepared statements and multi-statement DDL.
4. **The Data API must stay off.** See below — this is the security consequence and it is not
   optional.

## Security consequence — the Data API is disabled

Supabase auto-exposes every table in the `public` schema through PostgREST at
`https://tayflaukyjtcsyuivpxl.supabase.co/rest/v1/`, readable with the project's publishable
(anon) key. A table without row-level security is world-readable to anyone holding that key,
which by design ships in client-side code.

BhoomiRakshak is **government-internal, with no citizen surface, ever** — a locked decision. An
auto-generated public REST API over `projects`, `officers` (bcrypt hashes included),
`succession_claims` (named heirs and their claimed shares) and `audit_log` directly contradicts
it, and would be a fair finding against us at evaluation.

**Required before the schema is pushed to Supabase:** disable the Data API at
*Project Settings → Data API → Exposed schemas*, removing `public`. Access is then only through
the Postgres connection string that our FastAPI backend holds, which is the intended path.
Enabling RLS on all fifteen tables is the alternative; disabling the API outright is fewer moving
parts and there is no client that needs it.
