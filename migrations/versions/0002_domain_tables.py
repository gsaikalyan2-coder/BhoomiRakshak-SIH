"""Phase 1 — domain tables: projects (+geom), risk_history, status_log,
succession_claims, succession_risk, project_dependencies.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        # identity
        sa.Column(
            "ulpin",
            sa.String(17),
            primary_key=True,
            comment="14-digit DILRMP ULPIN, formatted SS-DDD-TTT-VVVVVV.",
        ),
        sa.Column("project_name", sa.String(160), nullable=False),
        sa.Column("project_type", sa.String(64), nullable=False),
        sa.Column("implementing_agency", sa.String(96), nullable=False),
        # location
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("district", sa.String(64), nullable=False),
        sa.Column("taluk", sa.String(80), nullable=False),
        sa.Column("village", sa.String(80), nullable=False),
        sa.Column("admin_unit_id", sa.Integer, nullable=False),
        sa.Column("latitude", sa.Numeric(9, 5), nullable=False),
        sa.Column("longitude", sa.Numeric(9, 5), nullable=False),
        sa.Column("geom", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        # timeline
        sa.Column("notification_date", sa.Date, nullable=False),
        sa.Column("expected_completion_date", sa.Date, nullable=False),
        sa.Column("actual_completion_date", sa.Date, nullable=True),
        sa.Column("planned_duration_days", sa.Integer, nullable=False),
        # scale
        sa.Column("land_area_acres", sa.Numeric(10, 2), nullable=False),
        sa.Column("no_affected_families", sa.Integer, nullable=False),
        sa.Column("no_landowners", sa.Integer, nullable=False),
        # ownership / title
        sa.Column("ownership_fragmentation_index", sa.Numeric(6, 3), nullable=False),
        sa.Column("ownership_dispute_flag", sa.Boolean, nullable=False),
        sa.Column("no_ownership_disputes", sa.Integer, nullable=False),
        sa.Column("title_clarity_status", sa.String(16), nullable=False),
        # compensation
        sa.Column("circle_rate_per_acre_lakhs", sa.Numeric(12, 2), nullable=False),
        sa.Column("compensation_fair_value_lakhs", sa.Numeric(14, 2), nullable=False),
        sa.Column("compensation_amount_sanctioned_lakhs", sa.Numeric(14, 2), nullable=False),
        sa.Column("compensation_amount_disbursed_lakhs", sa.Numeric(14, 2), nullable=False),
        sa.Column("compensation_disbursed_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("compensation_gap_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("compensation_dispute_flag", sa.Boolean, nullable=False),
        sa.Column("no_compensation_appeals", sa.Integer, nullable=False),
        # litigation
        sa.Column("no_legal_disputes", sa.Integer, nullable=False),
        sa.Column("legal_dispute_stage", sa.String(24), nullable=False),
        sa.Column("court_stay_flag", sa.Boolean, nullable=False),
        sa.Column("days_since_dispute_filed", sa.Integer, nullable=False),
        # rehabilitation & resettlement
        sa.Column("rehab_plan_approved_flag", sa.Boolean, nullable=False),
        sa.Column("rehab_progress_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("resettlement_site_ready_flag", sa.Boolean, nullable=False),
        sa.Column("no_families_resettled", sa.Integer, nullable=False),
        # administrative
        sa.Column("approval_stage", sa.String(48), nullable=False),
        sa.Column("days_in_current_stage", sa.Integer, nullable=False),
        sa.Column("no_pending_clearances", sa.Integer, nullable=False),
        sa.Column("environmental_clearance_status", sa.String(24), nullable=False),
        sa.Column("forest_clearance_status", sa.String(24), nullable=False),
        # label / cohort
        sa.Column("is_closed_project", sa.Boolean, nullable=False),
        sa.Column("historical_delay_days", sa.Integer, nullable=True),
        sa.Column(
            "is_delayed",
            sa.Boolean,
            nullable=True,
            comment="Training label, 'became overdue'. NULL for the 300 ongoing projects.",
        ),
        sa.Column("delay_stage", sa.String(32), nullable=True),
        # audit columns kept deliberately; they are on the Phase 2 model drop-list
        sa.Column(
            "latent_risk_audit",
            sa.Numeric(6, 4),
            nullable=False,
            comment="Generator ground truth. On the mandatory model drop-list — never a feature.",
        ),
        sa.Column(
            "top_driver_audit",
            sa.String(48),
            nullable=False,
            comment="Generator ground truth. On the mandatory model drop-list — never a feature.",
        ),
        sa.Column("assigned_field_officer_id", sa.String(24), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["admin_unit_id"], ["admin_units.id"], name="fk_projects_admin_unit"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_field_officer_id"], ["officers.officer_id"], name="fk_projects_officer"
        ),
        sa.CheckConstraint(
            "title_clarity_status IN ('Clear', 'Partial', 'Disputed')",
            name="ck_projects_title_clarity",
        ),
        sa.CheckConstraint(
            "(is_closed_project AND is_delayed IS NOT NULL) "
            "OR (NOT is_closed_project AND is_delayed IS NULL)",
            name="ck_projects_label_only_when_closed",
        ),
    )
    op.create_index("ix_projects_admin_unit_id", "projects", ["admin_unit_id"])
    op.create_index("ix_projects_officer", "projects", ["assigned_field_officer_id"])
    op.create_index("ix_projects_district", "projects", ["state", "district"])
    op.create_index("ix_projects_is_closed", "projects", ["is_closed_project"])
    op.create_index("ix_projects_approval_stage", "projects", ["approval_stage"])
    op.create_index("ix_projects_geom", "projects", ["geom"], postgresql_using="gist")

    op.create_table(
        "risk_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("compensation_disbursed_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("rehab_progress_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("days_in_current_stage", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_risk_history_project", ondelete="CASCADE"
        ),
        sa.UniqueConstraint("ulpin", "snapshot_date", name="uq_risk_history_snapshot"),
    )
    op.create_index("ix_risk_history_ulpin", "risk_history", ["ulpin"])

    op.create_table(
        "status_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("desk", sa.String(48), nullable=False),
        sa.Column("stage", sa.String(48), nullable=False),
        sa.Column("entered_on", sa.Date, nullable=False),
        sa.Column("exited_on", sa.Date, nullable=True),
        sa.Column("days_at_desk", sa.Integer, nullable=False),
        sa.Column("is_current", sa.Boolean, nullable=False),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_status_log_project", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "exited_on IS NULL OR exited_on >= entered_on", name="ck_status_log_dates"
        ),
    )
    op.create_index("ix_status_log_ulpin", "status_log", ["ulpin"])
    op.create_index("ix_status_log_stage", "status_log", ["ulpin", "stage"])
    op.create_index(
        "ix_status_log_current",
        "status_log",
        ["ulpin"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "succession_claims",
        sa.Column("claim_id", sa.String(40), primary_key=True),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("claimant_name", sa.String(120), nullable=False),
        sa.Column("relation_to_recorded_owner", sa.String(48), nullable=False),
        sa.Column("blood_relation", sa.Boolean, nullable=False),
        sa.Column("proof_status", sa.String(16), nullable=False),
        sa.Column("proof_document", sa.String(96), nullable=True),
        sa.Column("claimed_share_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False),
        sa.Column("claim_filed_on", sa.Date, nullable=False),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_succession_claims_project", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "proof_status IN ('Documented', 'Undocumented', 'Contested')",
            name="ck_succession_claims_proof",
        ),
    )
    op.create_index("ix_succession_claims_ulpin", "succession_claims", ["ulpin"])

    op.create_table(
        "succession_risk",
        sa.Column("ulpin", sa.String(17), primary_key=True),
        sa.Column("heir_claim_count", sa.Integer, nullable=False),
        sa.Column("undocumented_claims", sa.Integer, nullable=False),
        sa.Column("contested_claims", sa.Integer, nullable=False),
        sa.Column("share_total_pct", sa.Numeric(7, 2), nullable=False),
        sa.Column("succession_risk_band", sa.String(8), nullable=False),
        sa.Column("succession_reason", sa.String(160), nullable=False),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_succession_risk_project", ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "succession_risk_band IN ('High', 'Medium', 'Low')", name="ck_succession_risk_band"
        ),
    )
    op.create_index("ix_succession_risk_band", "succession_risk", ["succession_risk_band"])

    op.create_table(
        "project_dependencies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("upstream_ulpin", sa.String(17), nullable=False),
        sa.Column("downstream_ulpin", sa.String(17), nullable=False),
        sa.Column("dependency_type", sa.String(48), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.ForeignKeyConstraint(
            ["upstream_ulpin"],
            ["projects.ulpin"],
            name="fk_dependencies_upstream",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["downstream_ulpin"],
            ["projects.ulpin"],
            name="fk_dependencies_downstream",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("upstream_ulpin", "downstream_ulpin", name="uq_dependency_edge"),
        sa.CheckConstraint("upstream_ulpin <> downstream_ulpin", name="ck_dependency_no_self_edge"),
    )
    op.create_index("ix_dependencies_upstream", "project_dependencies", ["upstream_ulpin"])
    op.create_index("ix_dependencies_downstream", "project_dependencies", ["downstream_ulpin"])


def downgrade() -> None:
    op.drop_table("project_dependencies")
    op.drop_table("succession_risk")
    op.drop_table("succession_claims")
    op.drop_table("status_log")
    op.drop_table("risk_history")
    op.drop_index("ix_projects_geom", table_name="projects")
    op.drop_table("projects")
