from __future__ import annotations

from pathlib import Path

import pytest
from alembic.config import Config
from alembic.util import CommandError
from sqlalchemy import create_engine, inspect, text

from alembic import command
from portfolio_agent.bootstrap import project_root


def _config(database_url: str) -> Config:
    config = Config(str(project_root() / "alembic.ini"))
    config.set_main_option("script_location", str(project_root() / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_0009_empty_schema_downgrades_and_reupgrades(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'research-roundtrip.db'}"
    config = _config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    assert inspect(engine).has_table("company_research_runs")
    assert "research_run_id" in {
        column["name"] for column in inspect(engine).get_columns("profile_versions")
    }
    engine.dispose()

    command.downgrade(config, "0008")
    engine = create_engine(database_url)
    assert not inspect(engine).has_table("company_research_runs")
    assert "research_run_id" not in {
        column["name"] for column in inspect(engine).get_columns("profile_versions")
    }
    assert engine.connect().execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()

    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0010"
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    engine.dispose()


def test_0009_populated_downgrade_fails_before_schema_mutation(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'research-populated.db'}"
    config = _config(database_url)
    command.upgrade(config, "head")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO companies "
                "(id, canonical_name, normalized_name, resolution_status, classification, "
                "created_at) "
                "VALUES ('co_test', 'Test', 'test', 'resolved', 'public', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO research_templates (id, key, name, created_at) "
                "VALUES ('rt_test', 'test', 'Test', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO research_template_versions "
                "(id, template_id, version, objective, required_capabilities_json, "
                "optional_capabilities_json, claim_keys_json, budgets_json, sha256, published_at) "
                "VALUES ('rtv_test', 'rt_test', '1', 'Test', '[]', '[]', '[]', '{}', "
                "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', "
                "CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO research_cases "
                "(id, company_id, template_version_id, purpose, classification, status, "
                "created_by, created_at, updated_at) VALUES "
                "('case_test', 'co_test', 'rtv_test', 'Test research', 'public', 'ready', "
                "'Reviewer', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO company_research_runs "
                "(id, research_case_id, company_id, request_fingerprint, reporting_cutoff, "
                "source_policy_version, model, prompt_version, status, budgets_json, usage_json, "
                "coverage_json, created_by, created_at, updated_at) VALUES "
                "('crun_test', 'case_test', 'co_test', "
                "'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', "
                "'2026-08-27', 'v1', 'gpt-5.4-mini', 'v1', 'pending', '{}', '{}', '{}', "
                "'Reviewer', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()

    with pytest.raises(CommandError, match="cannot be downgraded"):
        command.downgrade(config, "0008")
    engine = create_engine(database_url)
    assert inspect(engine).has_table("company_research_runs")
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0009"
        )
    engine.dispose()
