from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from pytest import MonkeyPatch
from sqlalchemy import Engine, create_engine, inspect

from alembic import command
from portfolio_agent import models  # noqa: F401
from portfolio_agent.bootstrap import project_root
from portfolio_agent.db import Base


def _schema_contract(engine: Engine) -> dict[str, object]:
    inspector = inspect(engine)
    tables = sorted(Base.metadata.tables)
    return {
        "tables": tables,
        "columns": {
            table: sorted(
                (column["name"], column["nullable"]) for column in inspector.get_columns(table)
            )
            for table in tables
        },
        "unique_constraints": {
            table: sorted(
                tuple(sorted(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table)
            )
            for table in tables
        },
        "indexes": {
            table: sorted(
                (
                    index["name"],
                    bool(index["unique"]),
                    tuple(index["column_names"]),
                )
                for index in inspector.get_indexes(table)
            )
            for table in tables
        },
    }


def test_metadata_and_alembic_head_have_equivalent_schema(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    metadata_engine = create_engine(f"sqlite:///{tmp_path / 'metadata.db'}")
    Base.metadata.create_all(metadata_engine)

    migration_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("PORTFOLIO_DATABASE_URL", migration_url)
    config = Config(str(project_root() / "alembic.ini"))
    command.upgrade(config, "head")
    command.check(config)
    migration_engine = create_engine(migration_url)

    assert _schema_contract(metadata_engine) == _schema_contract(migration_engine)
    extraction_columns = {
        column["name"] for column in inspect(migration_engine).get_columns("extractions")
    }
    assert {"evidence_span", "abstain_reason"} <= extraction_columns

    metadata_engine.dispose()
    migration_engine.dispose()
