from __future__ import annotations

import os
from logging.config import fileConfig

from alembic.util import CommandError
from sqlalchemy import Connection, engine_from_config, inspect, pool, text

from alembic import context
from portfolio_agent import models  # noqa: F401
from portfolio_agent.db import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.getenv("PORTFOLIO_DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def _preflight_legacy_name_downgrade(connection: Connection) -> None:
    """Reject a lossy 0001 downgrade before any revision mutates the database."""
    migration_context = context.get_context()
    if "destination_rev" not in migration_context.opts:
        # Commands such as ``alembic check`` have no migration destination.
        return
    migration_fn = getattr(migration_context, "_migrations_fn", None)
    if migration_fn is None:
        return
    planned_steps = tuple(migration_fn(migration_context.get_current_heads(), migration_context))
    crosses_legacy_boundary = any(
        step.is_downgrade and "0002" in step.from_revisions and "0001" in step.to_revisions
        for step in planned_steps
    )
    if not crosses_legacy_boundary:
        return
    inspector = inspect(connection)
    if not inspector.has_table("companies") or not inspector.has_table("alembic_version"):
        return
    current = connection.execute(
        text("SELECT version_num FROM alembic_version")
    ).scalar_one_or_none()
    if current in {None, "0001"}:
        return
    duplicate = connection.execute(
        text(
            "SELECT normalized_name, COUNT(*) AS duplicate_count FROM companies "
            "GROUP BY normalized_name HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise CommandError(
            "The requested downgrade crosses 0002 to 0001 and is not losslessly reversible while "
            "companies share a "
            "normalized name. The database was not modified; resolve or archive the duplicate "
            "canonical identities before retrying."
        )


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        context.configure(
            connection=supplied_connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        _preflight_legacy_name_downgrade(supplied_connection)
        with context.begin_transaction():
            context.run_migrations()
        return

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        _preflight_legacy_name_downgrade(connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
