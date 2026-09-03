"""BhoomiRakshak — Phase 1 seed loader.

Loads the eight rev-3 CSVs in ml/data/ into the Postgres+PostGIS schema created by
`alembic upgrade head`, in foreign-key order, inside a single transaction:

    admin_units -> district_boundaries -> officers -> projects -> risk_history
    -> status_log -> succession_claims -> succession_risk -> project_dependencies

Rules enforced here:
  * Officer passwords are hashed with **bcrypt**. The shipped `password_sha256_demo`
    column is a placeholder and is never read.
  * Every project is resolved to an `admin_units` row by (state, district, taluk, village);
    an unresolved project aborts the load rather than seeding an orphan.
  * `geom` is built with ST_SetSRID(ST_MakePoint(longitude, latitude), 4326).
  * District boundaries are derived as the buffered convex hull of each district's village
    centroids. They are an approximation and are labelled `derived-village-hull`.

Usage:  python scripts/seed.py [--truncate]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from passlib.context import CryptContext
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "ml" / "data"

load_dotenv(REPO_ROOT / ".env")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Codes carry leading zeros; they must never be parsed as integers.
CODE_COLUMNS = ["state_code", "district_code", "taluk_code", "village_code"]

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

TABLES_IN_LOAD_ORDER = [
    "project_dependencies",
    "succession_risk",
    "succession_claims",
    "status_log",
    "risk_history",
    "projects",
    "officers",
    "district_boundaries",
    "admin_units",
]


def read_csv(name: str, **kwargs) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        raise SystemExit(f"missing dataset file: {path}")
    return pd.read_csv(path, **kwargs)


def demo_password(officer_id: str) -> str:
    """Deterministic demo password so seeded accounts can be logged into in Phase 3.

    Not a secret: these are seeded demo accounts on a government-internal prototype and
    the credential is shown on the login screen by design.
    """
    return f"{officer_id.lower()}"


def truncate_all(conn: Connection) -> None:
    for table in TABLES_IN_LOAD_ORDER:
        conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    conn.execute(text("ALTER SEQUENCE admin_units_id_seq RESTART WITH 1"))
    conn.execute(text("ALTER SEQUENCE district_boundaries_id_seq RESTART WITH 1"))


def load_admin_units(conn: Connection) -> pd.DataFrame:
    df = read_csv("admin_units", dtype={c: str for c in CODE_COLUMNS})
    df["state_code"] = df["state_code"].str.zfill(2)
    df["district_code"] = df["district_code"].str.zfill(3)
    df["taluk_code"] = df["taluk_code"].str.zfill(2)
    df["village_code"] = df["village_code"].str.zfill(3)
    rows = df.to_dict("records")
    conn.execute(
        text("""
            INSERT INTO admin_units (
                state, state_code, district, district_code, taluk, taluk_code,
                village, village_code, latitude, longitude, no_plots, no_khatiyans,
                no_tenants, ri_circle, revenue_inspector, tehsildar, geom
            ) VALUES (
                :state, :state_code, :district, :district_code, :taluk, :taluk_code,
                :village, :village_code, :latitude, :longitude, :no_plots, :no_khatiyans,
                :no_tenants, :ri_circle, :revenue_inspector, :tehsildar,
                ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)
            )
            """),
        rows,
    )
    return df


def load_district_boundaries(conn: Connection) -> None:
    """Approximate district polygons from the villages that sit inside them.

    A real deployment loads survey-of-India district GeoJSON; that file is not part of the
    rev-3 dataset, so the choropleth is backed by the convex hull of each district's village
    centroids, buffered by ~0.05 degrees so single- and two-village districts still form a
    polygon. Provenance is stored in district_boundaries.source and shown in the UI.
    """
    conn.execute(text("""
            INSERT INTO district_boundaries (state, state_code, district, district_code,
                                             source, geom)
            SELECT
                state,
                state_code,
                district,
                district_code,
                'derived-village-hull',
                ST_Buffer(ST_ConvexHull(ST_Collect(geom)), 0.05)
            FROM admin_units
            GROUP BY state, state_code, district, district_code
            """))


def load_officers(conn: Connection) -> pd.DataFrame:
    df = read_csv("officers")
    if "password_sha256_demo" in df.columns:
        df = df.drop(columns=["password_sha256_demo"])  # placeholder — never loaded
    records = []
    for row in df.to_dict("records"):
        records.append(
            {
                "officer_id": row["officer_id"],
                "full_name": row["full_name"],
                "role": row["role"],
                "state": None if pd.isna(row["state"]) else row["state"],
                "district": None if pd.isna(row["district"]) else row["district"],
                "designation": row["designation"],
                "password_hash": pwd_context.hash(demo_password(row["officer_id"])),
            }
        )
    conn.execute(
        text("""
            INSERT INTO officers (officer_id, full_name, role, state, district,
                                  designation, password_hash)
            VALUES (:officer_id, :full_name, :role, :state, :district,
                    :designation, :password_hash)
            """),
        records,
    )
    return df


def load_projects(conn: Connection, admin_units: pd.DataFrame) -> pd.DataFrame:
    # 'None' is a real ordinal level of legal_dispute_stage (no dispute on file), not a
    # missing value; pandas would otherwise read the literal string as NaN.
    df = read_csv("projects", keep_default_na=True)
    df["legal_dispute_stage"] = df["legal_dispute_stage"].fillna("None")

    unit_ids = dict(
        conn.execute(
            text(
                "SELECT state || '|' || district || '|' || taluk || '|' || village, id "
                "FROM admin_units"
            )
        ).all()
    )
    keys = df["state"] + "|" + df["district"] + "|" + df["taluk"] + "|" + df["village"]
    df["admin_unit_id"] = keys.map(unit_ids)
    unresolved = df[df["admin_unit_id"].isna()]
    if len(unresolved):
        raise SystemExit(
            f"{len(unresolved)} project(s) do not resolve to an admin_units row, "
            f"first: {unresolved.iloc[0]['ulpin']}"
        )

    df = df.astype(object).where(pd.notna(df), None)
    columns = [
        "ulpin",
        "project_name",
        "project_type",
        "implementing_agency",
        "state",
        "district",
        "taluk",
        "village",
        "admin_unit_id",
        "latitude",
        "longitude",
        "notification_date",
        "expected_completion_date",
        "actual_completion_date",
        "planned_duration_days",
        "land_area_acres",
        "no_affected_families",
        "no_landowners",
        "ownership_fragmentation_index",
        "ownership_dispute_flag",
        "no_ownership_disputes",
        "title_clarity_status",
        "circle_rate_per_acre_lakhs",
        "compensation_fair_value_lakhs",
        "compensation_amount_sanctioned_lakhs",
        "compensation_amount_disbursed_lakhs",
        "compensation_disbursed_pct",
        "compensation_gap_pct",
        "compensation_dispute_flag",
        "no_compensation_appeals",
        "no_legal_disputes",
        "legal_dispute_stage",
        "court_stay_flag",
        "days_since_dispute_filed",
        "rehab_plan_approved_flag",
        "rehab_progress_pct",
        "resettlement_site_ready_flag",
        "no_families_resettled",
        "approval_stage",
        "days_in_current_stage",
        "no_pending_clearances",
        "environmental_clearance_status",
        "forest_clearance_status",
        "is_closed_project",
        "historical_delay_days",
        "is_delayed",
        "delay_stage",
        "latent_risk_audit",
        "top_driver_audit",
        "assigned_field_officer_id",
    ]
    placeholders = ", ".join(f":{c}" for c in columns)
    conn.execute(
        text(
            f"INSERT INTO projects ({', '.join(columns)}, geom) "
            f"VALUES ({placeholders}, ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326))"
        ),
        df[columns].to_dict("records"),
    )
    return df


def load_simple(conn: Connection, name: str, columns: list[str]) -> pd.DataFrame:
    df = read_csv(name)
    df = df.astype(object).where(pd.notna(df), None)
    placeholders = ", ".join(f":{c}" for c in columns)
    conn.execute(
        text(f"INSERT INTO {name} ({', '.join(columns)}) VALUES ({placeholders})"),
        df[columns].to_dict("records"),
    )
    return df


def verify_counts(conn: Connection) -> list[str]:
    problems: list[str] = []
    for table, expected in EXPECTED_ROWS.items():
        actual = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        status = "OK " if actual == expected else "FAIL"
        if actual != expected:
            problems.append(f"{table}: expected {expected}, got {actual}")
        print(f"  [{status}] {table:<22} {actual:>6} rows (expected {expected})")

    sha_survivors = conn.execute(
        text("SELECT count(*) FROM officers WHERE password_hash NOT LIKE '$2%'")
    ).scalar_one()
    print(
        f"  [{'OK ' if sha_survivors == 0 else 'FAIL'}] officers with non-bcrypt hash: {sha_survivors}"
    )
    if sha_survivors:
        problems.append("non-bcrypt password hashes present in officers")

    outside = conn.execute(text("""
            SELECT count(*)
            FROM projects p
            JOIN district_boundaries d
              ON d.state = p.state AND d.district = p.district
            WHERE NOT ST_Within(p.geom, d.geom)
            """)).scalar_one()
    print(
        f"  [{'OK ' if outside == 0 else 'FAIL'}] project pins outside their own district: {outside}"
    )
    if outside:
        problems.append(f"{outside} project pins fall outside their district polygon")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the BhoomiRakshak database.")
    parser.add_argument("--truncate", action="store_true", help="empty all tables before loading")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is not set — fill .env from .env.example first.")

    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        if args.truncate:
            truncate_all(conn)

        print("Loading reference data ...")
        admin_units = load_admin_units(conn)
        load_district_boundaries(conn)
        load_officers(conn)

        print("Loading projects and history ...")
        load_projects(conn, admin_units)
        load_simple(
            conn,
            "risk_history",
            [
                "ulpin",
                "snapshot_date",
                "risk_score",
                "compensation_disbursed_pct",
                "rehab_progress_pct",
                "days_in_current_stage",
            ],
        )
        load_simple(
            conn,
            "status_log",
            ["ulpin", "desk", "stage", "entered_on", "exited_on", "days_at_desk", "is_current"],
        )
        load_simple(
            conn,
            "succession_claims",
            [
                "claim_id",
                "ulpin",
                "claimant_name",
                "relation_to_recorded_owner",
                "blood_relation",
                "proof_status",
                "proof_document",
                "claimed_share_pct",
                "verification_status",
                "claim_filed_on",
            ],
        )
        load_simple(
            conn,
            "succession_risk",
            [
                "ulpin",
                "heir_claim_count",
                "undocumented_claims",
                "contested_claims",
                "share_total_pct",
                "succession_risk_band",
                "succession_reason",
            ],
        )
        load_simple(
            conn,
            "project_dependencies",
            ["upstream_ulpin", "downstream_ulpin", "dependency_type", "note"],
        )

        conn.execute(text("ANALYZE"))
        print("\nVerification:")
        problems = verify_counts(conn)

    if problems:
        print("\nSEED FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nSeed complete — zero integrity errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
