"""Traceable ingestion and normalized observed sales."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA raw")
    op.execute("CREATE SCHEMA core")
    op.create_table(
        "ingestion_loads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("fingerprint", sa.String(64)),
        sa.Column("reused_load_id", sa.Uuid()),
        sa.Column("parser_version", sa.String(30), nullable=False),
        sa.Column("selection", postgresql.JSONB(), nullable=False),
        sa.Column("sources", postgresql.JSONB(), nullable=False),
        sa.Column("records_processed", sa.BigInteger(), nullable=False),
        sa.Column("records_rejected", sa.BigInteger(), nullable=False),
        sa.Column("records_inserted", sa.BigInteger(), nullable=False),
        sa.Column("records_unchanged", sa.BigInteger(), nullable=False),
        sa.Column("error_code", sa.String(60)),
        sa.Column("error_message", sa.String(500)),
        sa.CheckConstraint("status IN ('running', 'completed', 'failed')", name="status"),
        sa.CheckConstraint(
            "records_processed >= 0 AND records_rejected >= 0 AND records_inserted >= 0 "
            "AND records_unchanged >= 0",
            name="counts",
        ),
        sa.ForeignKeyConstraint(["reused_load_id"], ["raw.ingestion_loads.id"]),
        sa.PrimaryKeyConstraint("id"),
        schema="raw",
    )
    op.create_index(
        "uq_completed_fingerprint",
        "ingestion_loads",
        ["fingerprint"],
        unique=True,
        schema="raw",
        postgresql_where=sa.text("status = 'completed' AND reused_load_id IS NULL"),
    )
    op.create_table(
        "products",
        sa.Column("item_id", sa.String(100), nullable=False),
        sa.Column("department_id", sa.String(100), nullable=False),
        sa.Column("category_id", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("item_id"),
        schema="core",
    )
    op.create_table(
        "stores",
        sa.Column("store_id", sa.String(100), nullable=False),
        sa.Column("state_id", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("store_id"),
        schema="core",
    )
    op.create_table(
        "sales",
        sa.Column("item_id", sa.String(100), nullable=False),
        sa.Column("store_id", sa.String(100), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("units_sold", sa.BigInteger(), nullable=False),
        sa.Column("load_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("units_sold >= 0", name="nonnegative_units"),
        sa.ForeignKeyConstraint(["item_id"], ["core.products.item_id"]),
        sa.ForeignKeyConstraint(["store_id"], ["core.stores.store_id"]),
        sa.ForeignKeyConstraint(["load_id"], ["raw.ingestion_loads.id"]),
        sa.PrimaryKeyConstraint("item_id", "store_id", "date"),
        schema="core",
    )
    op.create_index("ix_sales_load_id", "sales", ["load_id"], schema="core")


def downgrade() -> None:
    op.drop_table("sales", schema="core")
    op.drop_table("stores", schema="core")
    op.drop_table("products", schema="core")
    op.drop_table("ingestion_loads", schema="raw")
    op.execute("DROP SCHEMA core")
    op.execute("DROP SCHEMA raw")
