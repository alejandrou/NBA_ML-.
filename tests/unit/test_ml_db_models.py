"""The `ml` models and their frozen revision declare the same schema."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import CheckConstraint

from nba_data.db.models import ml
from nba_data.db.models.ml import ModelVersion, Prediction

REVISION = Path(__file__).resolve().parents[2] / "alembic" / "versions" / "0012_ml_predictions.py"
FROZEN_CONDITIONS = {
    "ck_ml_model_versions_sha256_format": "MODEL_VERSIONS_SHA256_FORMAT",
    "ck_ml_predictions_status": "PREDICTIONS_STATUS",
    "ck_ml_predictions_unavailable_reason": "PREDICTIONS_UNAVAILABLE_REASON",
    "ck_ml_predictions_favorite": "PREDICTIONS_FAVORITE",
    "ck_ml_predictions_probability_range": "PREDICTIONS_PROBABILITY_RANGE",
    "ck_ml_predictions_probabilities_sum": "PREDICTIONS_PROBABILITIES_SUM",
    "ck_ml_predictions_favorite_rule": "PREDICTIONS_FAVORITE_RULE",
    "ck_ml_predictions_status_fields": "PREDICTIONS_STATUS_FIELDS",
}


@pytest.fixture(scope="module")
def revision() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_ml_revision_under_test", REVISION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _checks() -> dict[str, CheckConstraint]:
    return {
        str(constraint.name): constraint
        for table in (ModelVersion.__table__, Prediction.__table__)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def test_every_check_is_frozen_in_the_revision() -> None:
    assert set(_checks()) == set(FROZEN_CONDITIONS)


@pytest.mark.parametrize(("name", "attribute"), FROZEN_CONDITIONS.items())
def test_frozen_conditions_match_the_models(
    revision: ModuleType, name: str, attribute: str
) -> None:
    assert str(_checks()[name].sqltext) == getattr(revision, attribute)
    assert getattr(ml, attribute) == getattr(revision, attribute)


def test_the_revision_imports_nothing_from_the_application() -> None:
    lines = REVISION.read_text(encoding="utf-8").splitlines()

    assert [line for line in lines if line.startswith(("import ", "from ")) and "nba_data" in line] == []


def test_a_single_active_model_is_a_partial_unique_index() -> None:
    [index] = [
        index
        for index in ModelVersion.__table__.indexes
        if index.name == "uq_ml_model_versions_single_active"
    ]

    assert index.unique
    assert str(index.dialect_options["postgresql"]["where"]) == "is_active"


def test_probabilities_hold_six_decimals() -> None:
    column = Prediction.__table__.c.home_win_probability

    assert (column.type.precision, column.type.scale) == (7, 6)
