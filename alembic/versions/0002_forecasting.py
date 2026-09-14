"""Forecast protocol runs, evaluated predictions and metrics.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA analytics")
    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("source_loads", pg.JSONB(), nullable=False),
        sa.Column("data_fingerprint", sa.String(64)),
        sa.Column("selection", pg.JSONB(), nullable=False),
        sa.Column("train_start", sa.Date(), nullable=False),
        sa.Column("train_end", sa.Date(), nullable=False),
        sa.Column("cutoff", sa.Date(), nullable=False),
        sa.Column("horizon", sa.Integer(), nullable=False),
        sa.Column("protocol_version", sa.String(20), nullable=False),
        sa.Column("features_version", sa.String(20), nullable=False),
        sa.Column("method", sa.String(40), nullable=False),
        sa.Column("configuration", pg.JSONB(), nullable=False),
        sa.Column("random_state", sa.Integer(), nullable=False),
        sa.Column("versions", pg.JSONB(), nullable=False),
        sa.Column("selected_method", sa.String(40)),
        sa.Column("selected_at", sa.DateTime(timezone=True)),
        sa.Column("decision", pg.JSONB()),
        sa.Column("stages", pg.JSONB(), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("error_message", sa.String(500)),
        sa.Column("error_details", pg.JSONB()),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="status"),
        sa.CheckConstraint("horizon = 14", name="horizon"),
        schema="analytics",
    )
    op.create_index(
        "ix_forecast_runs_completed", "forecast_runs", ["status", "finished_at"], schema="analytics"
    )
    op.create_table(
        "forecasts",
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("analytics.forecast_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stage", sa.String(20), primary_key=True),
        sa.Column("method", sa.String(40), primary_key=True),
        sa.Column("store_id", sa.String(100), primary_key=True),
        sa.Column("item_id", sa.String(100), primary_key=True),
        sa.Column("target_date", sa.Date(), primary_key=True),
        sa.Column("cutoff", sa.Date(), nullable=False),
        sa.Column("horizon_step", sa.Integer(), nullable=False),
        sa.Column("predicted_units", sa.Float(), nullable=False),
        sa.Column("actual_units", sa.Float(), nullable=False),
        sa.Column("volume_segment", sa.String(10), nullable=False),
        sa.Column("intermittency_segment", sa.String(10), nullable=False),
        sa.CheckConstraint("horizon_step BETWEEN 1 AND 14", name="horizon_step"),
        sa.CheckConstraint(
            "predicted_units >= 0 AND predicted_units < 'Infinity'::float8",
            name="finite_prediction",
        ),
        sa.CheckConstraint(
            "actual_units >= 0 AND actual_units < 'Infinity'::float8", name="finite_actual"
        ),
        schema="analytics",
    )
    op.create_table(
        "forecast_metrics",
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("analytics.forecast_runs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stage", sa.String(20), primary_key=True),
        sa.Column("method", sa.String(40), primary_key=True),
        sa.Column("scope", sa.String(20), primary_key=True),
        sa.Column("scope_value", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(20), primary_key=True),
        sa.Column("value", sa.Float()),
        sa.Column("numerator", sa.Float(), nullable=False),
        sa.Column("denominator", sa.Float(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.CheckConstraint(
            "(status = 'defined' AND value IS NOT NULL AND denominator > 0) OR "
            "(status = 'undefined' AND value IS NULL AND denominator = 0)",
            name="defined",
        ),
        schema="analytics",
    )


def downgrade():
    op.drop_table("forecast_metrics", schema="analytics")
    op.drop_table("forecasts", schema="analytics")
    op.drop_index("ix_forecast_runs_completed", table_name="forecast_runs", schema="analytics")
    op.drop_table("forecast_runs", schema="analytics")
    op.execute("DROP SCHEMA analytics")
