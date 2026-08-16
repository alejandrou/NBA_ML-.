"""The frozen migration SQL must still describe the rule the code enforces.

Revision 0006 carries its check-constraint conditions as literal text rather
than importing `nba_data.domain.team_codes`, so that re-running the revision
always produces the schema it produced the first time. The cost of freezing is
that the text can fall behind the module without anything noticing. This is the
thing that notices.

When it fails, the fix is *not* to edit revision 0006 — a revision that has been
applied anywhere must never change. Add a new revision that installs the current
generated condition, and repoint the constants below at it.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

from nba_data.domain.team_codes import reject_synthetic_team_code_sql

# `alembic/versions` is a script directory, not an importable package, so the
# revision is loaded from its path.
LATEST_CONSTRAINT_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "0006_synthetic_team_code_constraints.py"
)

# (snapshot attribute, column, nullable, mapped constraint name)
SNAPSHOTS = (
    (
        "TEAMS_BREF_ID_NOT_SYNTHETIC",
        "basketball_reference_team_id",
        True,
        "ck_core_teams_bref_id_not_synthetic",
    ),
    (
        "TEAMS_CURRENT_ABBREVIATION_NOT_SYNTHETIC",
        "current_abbreviation",
        True,
        "ck_core_teams_current_abbreviation_not_synthetic",
    ),
    (
        "TEAM_ALIASES_ABBREVIATION_NOT_SYNTHETIC",
        "abbreviation",
        False,
        "ck_core_team_aliases_abbreviation_not_synthetic",
    ),
    (
        "TEAM_SEASONS_ABBREV_NOT_SYNTHETIC",
        "team_abbreviation",
        False,
        "ck_core_team_seasons_abbrev_not_synthetic",
    ),
)


@pytest.fixture(scope="module")
def revision_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_revision_under_test", LATEST_CONSTRAINT_REVISION
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.unit
def test_the_revision_does_not_import_the_rule_it_froze() -> None:
    """Importing it would make an applied revision change retroactively."""

    import_lines = [
        line
        for line in LATEST_CONSTRAINT_REVISION.read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from ")) and "nba_data" in line
    ]

    assert import_lines == []


@pytest.mark.unit
@pytest.mark.parametrize(
    ("attribute", "column", "nullable", "constraint_name"),
    SNAPSHOTS,
    ids=[snapshot[3] for snapshot in SNAPSHOTS],
)
def test_frozen_condition_still_matches_the_generated_rule(
    revision_module: ModuleType,
    attribute: str,
    column: str,
    nullable: bool,
    constraint_name: str,
) -> None:
    frozen = revision_module._one_line(getattr(revision_module, attribute))
    generated = reject_synthetic_team_code_sql(column, nullable=nullable)

    assert frozen == generated, (
        f"{constraint_name} in {LATEST_CONSTRAINT_REVISION} no longer matches "
        "team_codes.py. Do not edit that revision — add a new one and repoint "
        "LATEST_CONSTRAINT_REVISION here."
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("attribute", "column", "nullable", "constraint_name"),
    SNAPSHOTS,
    ids=[snapshot[3] for snapshot in SNAPSHOTS],
)
def test_unwrapping_a_snapshot_cannot_corrupt_a_string_literal(
    revision_module: ModuleType,
    attribute: str,
    column: str,
    nullable: bool,
    constraint_name: str,
) -> None:
    """`_one_line` collapses whitespace, which is only safe if none is quoted."""

    literals = re.findall(r"'[^']*'", reject_synthetic_team_code_sql(column, nullable=nullable))

    assert literals
    assert [literal for literal in literals if any(char.isspace() for char in literal)] == []


@pytest.mark.unit
def test_the_revision_covers_every_constraint_the_models_declare() -> None:
    """A fifth guarded column added to the models needs a migration too."""

    from nba_data.db.models.core import Team, TeamAlias, TeamSeason

    declared = {
        constraint.name
        for table in (Team.__table__, TeamAlias.__table__, TeamSeason.__table__)
        for constraint in table.constraints
        if constraint.name is not None and constraint.name.endswith("_not_synthetic")
    }

    assert declared == {snapshot[3] for snapshot in SNAPSHOTS}
