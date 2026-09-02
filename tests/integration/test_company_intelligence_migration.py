from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.util import CommandError
from sqlalchemy import create_engine, inspect, text

from alembic import command
from portfolio_agent.bootstrap import project_root


def _config(database_url: str) -> Config:
    config = Config(str(project_root() / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_0008_is_additive_and_preserves_0007_company_rows(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'company-intelligence.db'}"
    config = _config(database_url)
    command.upgrade(config, "0007")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO companies "
                "(id, canonical_name, normalized_name, external_id, resolution_status, "
                "classification, created_at) VALUES "
                "('co_legacy', 'Legacy Synthetic Ltd', 'legacy synthetic ltd', NULL, "
                "'resolved', 'synthetic', :created_at)"
            ),
            {"created_at": datetime(2026, 8, 27, tzinfo=UTC)},
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    inspector = inspect(engine)
    assert {
        "research_templates",
        "research_template_versions",
        "research_cases",
        "intake_artifacts",
        "company_domains",
        "company_domain_decisions",
        "company_identifier_decisions",
        "profile_versions",
    } <= set(inspector.get_table_names())
    assert {"entity_type", "jurisdiction", "lifecycle_status"} <= {
        column["name"] for column in inspector.get_columns("companies")
    }
    with engine.connect() as connection:
        legacy = connection.execute(
            text(
                "SELECT canonical_name, resolution_status, entity_type, jurisdiction, "
                "lifecycle_status FROM companies WHERE id = 'co_legacy'"
            )
        ).one()
        assert tuple(legacy) == ("Legacy Synthetic Ltd", "resolved", None, None, None)
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_0008_empty_schema_can_downgrade_and_reupgrade(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'empty-round-trip.db'}"
    config = _config(database_url)
    command.upgrade(config, "head")
    command.downgrade(config, "0007")
    engine = create_engine(database_url)
    assert not inspect(engine).has_table("research_cases")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0007"
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert inspect(engine).has_table("research_cases")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0010"
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_0008_downgrade_fails_before_mutation_when_slice_data_exists(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'held-downgrade.db'}"
    config = _config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO research_templates (id, key, name, created_at) VALUES "
                "('rt_core', 'core_company_profile', 'Core company profile', :created_at)"
            ),
            {"created_at": datetime(2026, 8, 27, tzinfo=UTC)},
        )
    engine.dispose()

    with pytest.raises(CommandError, match="company-intelligence records"):
        command.downgrade(config, "0007")

    engine = create_engine(database_url)
    assert inspect(engine).has_table("research_templates")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0008"
        )
        assert connection.execute(text("SELECT count(*) FROM research_templates")).scalar_one() == 1
    engine.dispose()


def test_0008_downgrade_rejects_populated_company_metadata_before_mutation(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'held-company-metadata.db'}"
    config = _config(database_url)
    command.upgrade(config, "0007")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO companies "
                "(id, canonical_name, normalized_name, external_id, resolution_status, "
                "classification, created_at) VALUES "
                "('co_metadata', 'Metadata Synthetic Ltd', 'metadata synthetic ltd', NULL, "
                "'unresolved', 'synthetic', :created_at)"
            ),
            {"created_at": datetime(2026, 8, 27, tzinfo=UTC)},
        )
    engine.dispose()
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE companies SET entity_type = 'registered', jurisdiction = 'EW', "
                "lifecycle_status = 'candidate' WHERE id = 'co_metadata'"
            )
        )
    engine.dispose()

    with pytest.raises(CommandError, match="company-intelligence records"):
        command.downgrade(config, "0007")

    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0008"
        )
        assert connection.execute(
            text(
                "SELECT entity_type, jurisdiction, lifecycle_status FROM companies "
                "WHERE id = 'co_metadata'"
            )
        ).one() == ("registered", "EW", "candidate")
    assert inspect(engine).has_table("research_templates")
    engine.dispose()
