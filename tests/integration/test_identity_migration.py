from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.util import CommandError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from portfolio_agent.bootstrap import project_root
from portfolio_agent.identity import (
    is_valid_companies_house_number,
    parse_companies_house_identity,
)


def _alembic_config(database_url: str) -> Config:
    config = Config(str(project_root() / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_legacy_identity_survives_0001_0002_round_trip(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity-migration.db'}"
    config = _alembic_config(database_url)
    command.upgrade(config, "0001")
    engine = create_engine(database_url)
    created_at = datetime(2025, 6, 30, tzinfo=UTC)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO companies "
                "(id, canonical_name, normalized_name, external_id, resolution_status, "
                "classification, created_at) VALUES "
                "(:id, :name, :normalized, :external_id, :status, :classification, :created_at)"
            ),
            {
                "id": "co_legacy",
                "name": "Legacy Synthetic Ltd",
                "normalized": "legacy synthetic ltd",
                "external_id": "LEGACY-001",
                "status": "resolved",
                "classification": "synthetic",
                "created_at": created_at,
            },
        )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        migrated = connection.execute(
            text(
                "SELECT company_id, scheme, value FROM company_identifiers "
                "WHERE company_id = 'co_legacy'"
            )
        ).one()
    assert tuple(migrated) == ("co_legacy", "legacy", "LEGACY-001")
    assert not any(
        constraint["column_names"] == ["normalized_name"]
        for constraint in inspect(engine).get_unique_constraints("companies")
    )
    engine.dispose()

    command.downgrade(config, "0001")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        retained = connection.execute(
            text("SELECT canonical_name, external_id FROM companies WHERE id = 'co_legacy'")
        ).one()
    assert tuple(retained) == ("Legacy Synthetic Ltd", "LEGACY-001")
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM company_identifiers WHERE company_id = 'co_legacy'")
        ).scalar_one()
    assert count == 1
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
        assert inspect(engine).has_table("source_snapshots")
        assert inspect(engine).has_table("report_exports")
    engine.dispose()


def test_legacy_duplicate_external_ids_upgrade_as_unresolved_without_false_binding(
    tmp_path: Path,
) -> None:
    database_url = f"sqlite:///{tmp_path / 'duplicate-legacy-identifiers.db'}"
    config = _alembic_config(database_url)
    command.upgrade(config, "0001")
    engine = create_engine(database_url)
    created_at = datetime(2025, 6, 30, tzinfo=UTC)
    with engine.begin() as connection:
        for suffix, name in (("a", "Duplicate Alpha Ltd"), ("b", "Duplicate Beta Ltd")):
            connection.execute(
                text(
                    "INSERT INTO companies "
                    "(id, canonical_name, normalized_name, external_id, resolution_status, "
                    "classification, created_at) VALUES "
                    "(:id, :name, :normalized, 'DUPLICATE-001', 'resolved', 'synthetic', "
                    ":created_at)"
                ),
                {
                    "id": f"co_{suffix}",
                    "name": name,
                    "normalized": name.casefold(),
                    "created_at": created_at,
                },
            )
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        statuses = connection.execute(
            text(
                "SELECT id, resolution_status FROM companies "
                "WHERE external_id = 'DUPLICATE-001' ORDER BY id"
            )
        ).all()
        identifiers = connection.execute(
            text(
                "SELECT count(*) FROM company_identifiers WHERE normalized_value = 'DUPLICATE-001'"
            )
        ).scalar_one()
        foreign_key_findings = connection.execute(text("PRAGMA foreign_key_check")).all()
    assert [tuple(row) for row in statuses] == [
        ("co_a", "unresolved"),
        ("co_b", "unresolved"),
    ]
    assert identifiers == 0
    assert foreign_key_findings == []
    engine.dispose()


@pytest.mark.parametrize("downgrade_target", ("0001", "base", "-9"))
def test_same_normalized_name_can_coexist_but_registry_number_is_unique(
    tmp_path: Path, downgrade_target: str
) -> None:
    database_url = f"sqlite:///{tmp_path / 'identity-constraints.db'}"
    config = _alembic_config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    created_at = datetime(2025, 6, 30, tzinfo=UTC)
    with engine.begin() as connection:
        for suffix in ("a", "b"):
            connection.execute(
                text(
                    "INSERT INTO companies "
                    "(id, canonical_name, normalized_name, external_id, resolution_status, "
                    "classification, created_at) VALUES "
                    "(:id, :name, 'same name ltd', NULL, 'resolved', 'synthetic', :created_at)"
                ),
                {"id": f"co_{suffix}", "name": f"Same Name Ltd {suffix}", "created_at": created_at},
            )
            connection.execute(
                text(
                    "INSERT INTO company_identifiers "
                    "(id, company_id, scheme, value, normalized_value, source_key, valid_from, "
                    "valid_to, reviewed, created_at) VALUES "
                    "(:id, :company_id, 'companies_house_number', :number, :number, "
                    "'companies_house', NULL, NULL, 1, :created_at)"
                ),
                {
                    "id": f"cid_{suffix}",
                    "company_id": f"co_{suffix}",
                    "number": "00000001" if suffix == "a" else "00000002",
                    "created_at": created_at,
                },
            )

    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO company_identifiers "
                "(id, company_id, scheme, value, normalized_value, source_key, valid_from, "
                "valid_to, reviewed, created_at) VALUES "
                "('cid_collision', 'co_b', 'companies_house_number', '00000001', "
                "'00000001', 'companies_house', NULL, NULL, 1, :created_at)"
            ),
            {"created_at": created_at},
        )

    with pytest.raises(CommandError, match="not losslessly reversible"):
        command.downgrade(config, downgrade_target)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0010"
        )
        assert connection.execute(text("SELECT count(*) FROM companies")).scalar_one() == 2
    assert inspect(engine).has_table("company_programme_memberships")
    engine.dispose()


def test_companies_house_number_parser_is_structural_and_conservative() -> None:
    assert is_valid_companies_house_number("1234567")
    assert is_valid_companies_house_number("SC123456")
    assert not is_valid_companies_house_number("ABC123")
    assert parse_companies_house_identity(
        "Example Synthetic Ltd SC123456", fallback_name="Fallback"
    ) == ("Example Synthetic Ltd", "SC123456")
    assert parse_companies_house_identity(
        "Example Synthetic Ltd INVALID", fallback_name="Fallback"
    ) == ("Example Synthetic Ltd INVALID", None)
