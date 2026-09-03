"""Phase 1 — scoring, intelligence and governance tables, plus the issue_resolutions view (E2).

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


ISSUE_RESOLUTIONS_VIEW = """
CREATE VIEW issue_resolutions AS
-- E2 "resolution timeline". status_log records the desk chain WITHIN a project's current
-- statutory stage only, so clearance of an earlier stage is established by the project having
-- moved past it (projects.approval_stage), and dated only where the dataset actually carries a
-- date. Every row states its own evidence in `evidence`; a clearance we cannot date returns
-- is_cleared = true with cleared_on = NULL rather than an invented date.
WITH stage_rank(stage, rank) AS (
    VALUES
        ('SIA Completed',                  0),
        ('Section 11 Notification Issued', 1),
        ('Award Declared',                 3),
        ('Compensation Disbursement',      4),
        ('R&R Implementation',             5),
        ('Possession Taken',               6)
),
issue_class(issue_class, issue_label, sort_order) AS (
    VALUES
        ('notification', 'Section 11 notification issued', 1),
        ('objection',    'Objections heard and disposed',  2),
        ('award',        'Award declared',                 3),
        ('compensation', 'Compensation disbursed',         4),
        ('rnr',          'R&R implemented',                5),
        ('possession',   'Possession taken',               6)
),
project_stage AS (
    SELECT
        p.ulpin,
        p.notification_date,
        p.actual_completion_date,
        p.approval_stage,
        sr.rank AS current_rank,
        cur.entered_current_stage_on,
        legal.legal_exit_on,
        legal.legal_is_current
    FROM projects p
    JOIN stage_rank sr ON sr.stage = p.approval_stage
    LEFT JOIN LATERAL (
        SELECT min(s.entered_on) AS entered_current_stage_on
        FROM status_log s
        WHERE s.ulpin = p.ulpin AND s.stage = p.approval_stage
    ) cur ON TRUE
    LEFT JOIN LATERAL (
        SELECT max(s.exited_on) AS legal_exit_on, bool_or(s.is_current) AS legal_is_current
        FROM status_log s
        WHERE s.ulpin = p.ulpin AND s.desk = 'Legal Cell'
    ) legal ON TRUE
)
SELECT
    ps.ulpin,
    c.issue_class,
    c.issue_label,
    c.sort_order,
    ps.approval_stage AS current_stage,
    x.status,
    x.cleared_on,
    (x.status = 'Cleared') AS is_cleared,
    CASE
        WHEN x.cleared_on IS NULL THEN NULL
        ELSE (x.cleared_on - ps.notification_date)
    END AS days_from_notification,
    x.evidence
FROM project_stage ps
CROSS JOIN issue_class c
CROSS JOIN LATERAL (
    SELECT
        CASE
            WHEN c.issue_class = 'possession' AND ps.actual_completion_date IS NOT NULL
                THEN 'Cleared'
            WHEN c.issue_class = 'objection' AND ps.legal_is_current THEN 'Open — at desk'
            WHEN c.issue_class = 'objection' AND ps.legal_exit_on IS NOT NULL THEN 'Cleared'
            WHEN c.sort_order < ps.current_rank THEN 'Cleared'
            WHEN c.sort_order = ps.current_rank THEN 'Open — at desk'
            ELSE 'Not reached'
        END AS status,
        CASE
            WHEN c.issue_class = 'objection' AND NOT coalesce(ps.legal_is_current, false)
                THEN ps.legal_exit_on
            WHEN c.issue_class = 'notification' AND ps.current_rank >= 1
                THEN ps.notification_date
            WHEN c.issue_class = 'possession' AND ps.actual_completion_date IS NOT NULL
                THEN ps.actual_completion_date
            WHEN c.sort_order < ps.current_rank AND c.sort_order = ps.current_rank - 1
                THEN ps.entered_current_stage_on
            ELSE NULL
        END AS cleared_on,
        CASE
            WHEN c.issue_class = 'objection' AND ps.legal_is_current
                THEN 'status_log: file currently at Legal Cell'
            WHEN c.issue_class = 'objection' AND ps.legal_exit_on IS NOT NULL
                THEN 'status_log: date the file left the Legal Cell desk'
            WHEN c.issue_class = 'notification' AND ps.current_rank >= 1
                THEN 'projects.notification_date'
            WHEN c.issue_class = 'possession' AND ps.actual_completion_date IS NOT NULL
                THEN 'projects.actual_completion_date'
            WHEN c.sort_order < ps.current_rank AND c.sort_order = ps.current_rank - 1
                THEN 'status_log: date the file entered the current stage'
            WHEN c.sort_order < ps.current_rank
                THEN 'stage passed — clearance date not captured in the source records'
            WHEN c.sort_order = ps.current_rank
                THEN 'status_log: current stage, still open'
            ELSE 'stage not yet reached'
        END AS evidence
) x;

COMMENT ON VIEW issue_resolutions IS
'E2 resolution timeline: per project, per statutory issue class (notification, objection, award, '
'compensation, R&R, possession) — whether it is cleared, open at a desk, or not yet reached, the '
'clearance date where the source records carry one, and the evidence for that judgement. Derived '
'from projects.approval_stage / notification_date / actual_completion_date and status_log.';
"""


def upgrade() -> None:
    op.create_table(
        "risk_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("model_version", sa.String(48), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("risk_band", sa.String(8), nullable=False),
        sa.Column("predicted_delay_stage", sa.String(32), nullable=True),
        sa.Column("stage_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("is_current", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_risk_scores_project", ondelete="CASCADE"
        ),
        sa.CheckConstraint("risk_score BETWEEN 0 AND 1", name="ck_risk_scores_range"),
        sa.CheckConstraint("risk_band IN ('High', 'Medium', 'Low')", name="ck_risk_scores_band"),
    )
    op.create_index("ix_risk_scores_ulpin", "risk_scores", ["ulpin"])
    op.create_index(
        "ix_risk_scores_current",
        "risk_scores",
        ["ulpin"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    op.create_table(
        "risk_reasons",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("risk_score_id", sa.Integer, nullable=False),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("feature_name", sa.String(64), nullable=False),
        sa.Column("display_label", sa.String(200), nullable=False),
        sa.Column("shap_contribution", sa.Numeric(8, 5), nullable=False),
        sa.Column("contribution_pct", sa.Numeric(6, 2), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(
            ["risk_score_id"], ["risk_scores.id"], name="fk_risk_reasons_score", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_risk_reasons_project", ondelete="CASCADE"
        ),
        sa.CheckConstraint("direction IN ('up', 'down')", name="ck_risk_reasons_direction"),
        sa.UniqueConstraint("risk_score_id", "rank", name="uq_risk_reasons_rank"),
    )
    op.create_index("ix_risk_reasons_score_id", "risk_reasons", ["risk_score_id"])
    op.create_index("ix_risk_reasons_ulpin", "risk_reasons", ["ulpin"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("risk_score_id", sa.Integer, nullable=True),
        sa.Column("factor_key", sa.String(64), nullable=False),
        sa.Column("action_text", sa.String(400), nullable=False),
        sa.Column("owner_desk", sa.String(48), nullable=False),
        sa.Column("sla_days", sa.Integer, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "narrative",
            sa.Text,
            nullable=True,
            comment="Flan-T5 phrasing. NULL means the deterministic action_text is displayed.",
        ),
        sa.Column("source", sa.String(8), nullable=False, server_default=sa.text("'rule'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_recommendations_project", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["risk_score_id"],
            ["risk_scores.id"],
            name="fk_recommendations_score",
            ondelete="SET NULL",
        ),
        sa.CheckConstraint("source IN ('rule', 'llm')", name="ck_recommendations_source"),
    )
    op.create_index("ix_recommendations_ulpin", "recommendations", ["ulpin"])
    op.create_index("ix_recommendations_score_id", "recommendations", ["risk_score_id"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("officer_id", sa.String(24), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("risk_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("threshold", sa.Numeric(5, 4), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("delivery_status", sa.String(16), nullable=False),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_alerts_project", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["officer_id"], ["officers.officer_id"], name="fk_alerts_officer"),
        sa.CheckConstraint("channel IN ('email', 'webhook', 'in_app')", name="ck_alerts_channel"),
        sa.CheckConstraint(
            "delivery_status IN ('pending', 'sent', 'failed')", name="ck_alerts_status"
        ),
    )
    op.create_index("ix_alerts_ulpin", "alerts", ["ulpin"])
    op.create_index("ix_alerts_officer_id", "alerts", ["officer_id"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])

    op.create_table(
        "annotations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("ulpin", sa.String(17), nullable=False),
        sa.Column("officer_id", sa.String(24), nullable=False),
        sa.Column("annotation_type", sa.String(32), nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["ulpin"], ["projects.ulpin"], name="fk_annotations_project", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["officer_id"], ["officers.officer_id"], name="fk_annotations_officer"
        ),
        sa.CheckConstraint(
            "annotation_type IN ('action_taken', 'escalated_to_legal_cell', 'note', "
            "'risk_override')",
            name="ck_annotations_type",
        ),
    )
    op.create_index("ix_annotations_ulpin", "annotations", ["ulpin"])
    op.create_index("ix_annotations_officer_id", "annotations", ["officer_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("actor_officer_id", sa.String(24), nullable=True),
        sa.Column("actor_role", sa.String(16), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("http_method", sa.String(8), nullable=True),
        sa.Column("path", sa.String(200), nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", postgresql.INET, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_officer_id"],
            ["officers.officer_id"],
            name="fk_audit_log_officer",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_audit_log_actor_officer_id", "audit_log", ["actor_officer_id"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    op.execute(ISSUE_RESOLUTIONS_VIEW)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS issue_resolutions")
    op.drop_table("audit_log")
    op.drop_table("annotations")
    op.drop_table("alerts")
    op.drop_table("recommendations")
    op.drop_table("risk_reasons")
    op.drop_table("risk_scores")
