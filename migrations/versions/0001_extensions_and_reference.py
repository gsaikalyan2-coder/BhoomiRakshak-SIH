"""Phase 1 — extensions, PostGIS, and reference tables (admin_units, officers, district_boundaries).

Revision ID: 0001
Revises:
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "admin_units",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("district", sa.String(64), nullable=False),
        sa.Column("district_code", sa.String(3), nullable=False),
        sa.Column("taluk", sa.String(80), nullable=False),
        sa.Column("taluk_code", sa.String(3), nullable=False),
        sa.Column("village", sa.String(80), nullable=False),
        sa.Column("village_code", sa.String(6), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 5), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 5), nullable=False),
        sa.Column("no_plots", sa.Integer, nullable=False),
        sa.Column("no_khatiyans", sa.Integer, nullable=False),
        sa.Column("no_tenants", sa.Integer, nullable=False),
        sa.Column("ri_circle", sa.String(80), nullable=False),
        sa.Column("revenue_inspector", sa.String(80), nullable=False),
        sa.Column("tehsildar", sa.String(80), nullable=False),
        sa.Column("geom", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.UniqueConstraint(
            "state_code",
            "district_code",
            "taluk_code",
            "village_code",
            name="uq_admin_units_codes",
        ),
        sa.UniqueConstraint("state", "district", "taluk", "village", name="uq_admin_units_names"),
    )
    op.create_index("ix_admin_units_state", "admin_units", ["state"])
    op.create_index("ix_admin_units_district", "admin_units", ["state", "district"])
    op.create_index("ix_admin_units_taluk", "admin_units", ["state", "district", "taluk"])
    op.create_index("ix_admin_units_geom", "admin_units", ["geom"], postgresql_using="gist")

    op.create_table(
        "district_boundaries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=False),
        sa.Column("district", sa.String(64), nullable=False),
        sa.Column("district_code", sa.String(3), nullable=False),
        sa.Column(
            "source",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'derived-village-hull'"),
            comment="Provenance of the polygon. 'derived-village-hull' = convex hull of the "
            "district's village centroids, buffered; it is an approximation and the UI "
            "must label it as such.",
        ),
        sa.Column("geom", Geometry("POLYGON", srid=4326, spatial_index=False), nullable=False),
        sa.UniqueConstraint("state_code", "district_code", name="uq_district_boundaries_code"),
    )
    op.create_index(
        "ix_district_boundaries_geom", "district_boundaries", ["geom"], postgresql_using="gist"
    )

    op.create_table(
        "officers",
        sa.Column("officer_id", sa.String(24), primary_key=True),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("state", sa.String(64), nullable=True),
        sa.Column("district", sa.String(64), nullable=True),
        sa.Column("designation", sa.String(120), nullable=False),
        sa.Column(
            "password_hash",
            sa.String(72),
            nullable=False,
            comment="bcrypt hash. The password_sha256_demo column shipped in officers.csv is a "
            "placeholder and is never loaded.",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("role IN ('admin', 'officer')", name="ck_officers_role"),
        sa.CheckConstraint("password_hash LIKE '$2%'", name="ck_officers_password_is_bcrypt"),
    )
    op.create_index("ix_officers_role", "officers", ["role"])
    op.create_index("ix_officers_district", "officers", ["state", "district"])


def downgrade() -> None:
    op.drop_table("officers")
    op.drop_index("ix_district_boundaries_geom", table_name="district_boundaries")
    op.drop_table("district_boundaries")
    op.drop_index("ix_admin_units_geom", table_name="admin_units")
    op.drop_table("admin_units")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS postgis")
