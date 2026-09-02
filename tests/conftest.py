from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from portfolio_agent.bootstrap import Runtime, create_runtime, project_root
from portfolio_agent.config import Settings


@pytest.fixture
def runtime(tmp_path: Path) -> Iterator[Runtime]:
    settings = Settings(
        project_root=project_root(),
        database_url=f"sqlite:///{tmp_path / 'portfolio-test.db'}",
        raw_data_dir=tmp_path / "raw",
        allow_external_llm=False,
        reviewer_name="Synthetic Test Reviewer",
    )
    created = create_runtime(settings)
    try:
        yield created
    finally:
        created.engine.dispose()
