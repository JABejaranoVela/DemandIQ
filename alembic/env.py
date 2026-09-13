from alembic import context
from demandiq.config import Settings
from demandiq.db import Base, make_engine


def run_migrations() -> None:
    options = {"target_metadata": Base.metadata, "include_schemas": True, "compare_type": True}
    if context.is_offline_mode():
        context.configure(
            url=Settings().connection_url(),
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            **options,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, **options)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = make_engine(Settings())
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, **options)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
