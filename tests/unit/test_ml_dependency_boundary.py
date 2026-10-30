"""scikit-learn works for `nba_data.ml`, and the API never imports it (WF-009).

`scikit-learn` is a runtime dependency only so `nba_data.ml` can fit and evaluate
models. The API serves stored forecasts and runs no model (F8-010), so nothing
the API or its query repositories can import, directly or through a shared
helper, may import it, its numerical stack, or `nba_data.ml` itself. The static
test walks that whole local import graph; the runtime test checks what starting
the app and serving a request actually load. A smoke test proves the installed
wheels fit and predict, since installing cleanly is not the same as working.
"""

from __future__ import annotations

import ast
import json
import math
import os
import subprocess
import sys
from collections import deque
from pathlib import Path

import pytest

import nba_data

FORBIDDEN_MODULES = ("sklearn", "numpy", "scipy", "joblib", "nba_data.ml")
GUARDED_PACKAGES = ("nba_data.api", "nba_data.db.repositories.queries")
SUBPROCESS_TIMEOUT_SECONDS = 60
MODULES_LINE_PREFIX = "MODULES "

# nba_data.__file__ is `.../src/nba_data/__init__.py`; parents[1] is `src/`, the
# root each `nba_data.*` dotted name resolves against.
SRC_ROOT = Path(nba_data.__file__).resolve().parents[1]


def _is_forbidden(name: str) -> bool:
    return any(name == module or name.startswith(f"{module}.") for module in FORBIDDEN_MODULES)


def _module_name(path: Path, *, src_root: Path) -> str:
    parts = path.relative_to(src_root).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _resolve(name: str, *, src_root: Path) -> Path | None:
    """The local source file importing `name` runs, or None for a third-party name."""

    if not name:
        return None
    base = src_root / Path(*name.split("."))
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py")
    if (base / "__init__.py").is_file():
        return base / "__init__.py"
    return None


def _imported_names(source: str, *, module_name: str, is_package: bool) -> set[str]:
    """Every module name a source imports, anywhere in it, relative imports resolved.

    `ast.walk` also reaches imports inside functions and `if TYPE_CHECKING:`
    blocks: a deferred import of the ML stack is still an API dependency on it.
    `from a import b` yields both `a` and `a.b`, because `b` may be a submodule
    (`from nba_data import ml`).
    """

    package_parts = module_name.split(".") if is_package else module_name.split(".")[:-1]
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                anchor = package_parts[: len(package_parts) - node.level + 1]
                base = ".".join([*anchor, node.module] if node.module else anchor)
            else:
                base = node.module or ""
            names.add(base)
            names.update(f"{base}.{alias.name}" for alias in node.names)
    return names


def _local_modules_run_by(name: str, *, src_root: Path) -> list[str]:
    """Importing `a.b.c` runs `a/__init__.py` and `a/b/__init__.py` before `a/b/c.py`."""

    parts = name.split(".")
    prefixes = (".".join(parts[:depth]) for depth in range(1, len(parts) + 1))
    return [prefix for prefix in prefixes if _resolve(prefix, src_root=src_root) is not None]


def _ml_import_chains(roots: list[str], *, src_root: Path) -> list[str]:
    """Every forbidden import reachable from `roots` through local modules, as a chain.

    A breadth-first walk over every local module the roots can import, lazily
    or not, including the package initializers each import runs. A forbidden
    name is a leaf: it is reported, never walked into.
    """

    reached_from: dict[str, str | None] = {}
    queue: deque[str] = deque()
    for root in roots:
        for module in _local_modules_run_by(root, src_root=src_root):
            if module not in reached_from:
                reached_from[module] = None
                queue.append(module)

    def chain(module: str) -> list[str]:
        links = [module]
        while (parent := reached_from[links[-1]]) is not None:
            links.append(parent)
        return links[::-1]

    violations: list[str] = []
    while queue:
        module = queue.popleft()
        path = _resolve(module, src_root=src_root)
        assert path is not None, module
        names = _imported_names(
            path.read_text(encoding="utf-8"),
            module_name=module,
            is_package=path.name == "__init__.py",
        )
        for name in sorted(names):
            if _is_forbidden(name):
                violations.append(" -> ".join([*chain(module), name]))
                continue
            for local in _local_modules_run_by(name, src_root=src_root):
                if local not in reached_from:
                    reached_from[local] = module
                    queue.append(local)
    return sorted(set(violations))


def _guarded_modules() -> list[str]:
    return [
        _module_name(path, src_root=SRC_ROOT)
        for package in GUARDED_PACKAGES
        for path in sorted((SRC_ROOT / Path(*package.split("."))).rglob("*.py"))
    ]


def _run_python(
    code: str, *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """A fresh interpreter, so modules this test process imported cannot mask or fake a result."""

    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ("import numpy as np\n", "numpy"),
        ("from sklearn.linear_model import LogisticRegression\n", "sklearn.linear_model"),
        ("from nba_data import ml\n", "nba_data.ml"),
        ("from ..ml.elo import EloRatings\n", "nba_data.ml.elo"),
        ("def fit() -> None:\n    import joblib\n", "joblib"),
        ("from scipy.special import expit\n", "scipy.special"),
    ),
)
def test_the_import_scan_flags_every_form_of_a_forbidden_import(source: str, expected: str) -> None:
    names = _imported_names(source, module_name="nba_data.api.app", is_package=False)

    assert expected in names
    assert _is_forbidden(expected)


@pytest.mark.unit
def test_the_import_scan_does_not_flag_the_platform_s_own_dependencies() -> None:
    source = "from nba_data.db.models import Team\nimport sqlalchemy\nfrom . import schemas\n"

    names = _imported_names(source, module_name="nba_data.api", is_package=True)

    assert names >= {"nba_data.db.models", "sqlalchemy", "nba_data.api.schemas"}
    assert not any(_is_forbidden(name) for name in names)


@pytest.mark.unit
def test_the_walk_follows_shared_helpers_and_package_initializers(tmp_path: Path) -> None:
    """The gap a per-directory scan leaves: an API module calls a helper outside the
    guarded trees whose function body imports scikit-learn, and the helper's
    package initializer imports numpy. Neither runs when the app is merely created.
    """

    files = {
        "pkg/__init__.py": "",
        "pkg/api/__init__.py": "",
        "pkg/api/app.py": "from ..db.session import create_engine\n",
        "pkg/db/__init__.py": "import numpy\n",
        "pkg/db/session.py": "def create_engine() -> None:\n    from sklearn import base\n",
        "pkg/unused.py": "import scipy\n",
    }
    for relative, source in files.items():
        (tmp_path / relative).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / relative).write_text(source, encoding="utf-8")

    assert _ml_import_chains(["pkg.api.app"], src_root=tmp_path) == [
        "pkg.api.app -> pkg.db -> numpy",
        "pkg.api.app -> pkg.db.session -> sklearn",
        "pkg.api.app -> pkg.db.session -> sklearn.base",
    ]


@pytest.mark.unit
def test_nothing_the_api_can_import_imports_the_ml_stack() -> None:
    roots = _guarded_modules()

    # Not vacuous: the roots cover both trees down to their leaf modules.
    assert {"nba_data.api.app", "nba_data.api.routers.teams"} <= set(roots)
    assert "nba_data.db.repositories.queries.teams" in roots

    assert _ml_import_chains(roots, src_root=SRC_ROOT) == []


@pytest.mark.unit
def test_starting_the_api_and_serving_a_request_loads_no_ml_module() -> None:
    # Lifespan builds an Engine but never connects; the URL still points nowhere
    # so no setting from `.env` can make this test reach a real database.
    env = {**os.environ, "DATABASE_URL": "postgresql+psycopg://nobody:nobody@127.0.0.1:9/none"}
    result = _run_python(
        "import json, sys\n"
        "from fastapi.testclient import TestClient\n"
        "from nba_data.api.app import create_app\n"
        "with TestClient(create_app()) as client:\n"
        "    assert client.get('/api/v1/health').status_code == 200\n"
        f"print({MODULES_LINE_PREFIX!r} + json.dumps(sorted(sys.modules)))\n",
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    [line] = [line for line in result.stdout.splitlines() if line.startswith(MODULES_LINE_PREFIX)]
    loaded = json.loads(line.removeprefix(MODULES_LINE_PREFIX))

    # Not vacuous: the subprocess ran the lifespan and the repositories it reads through.
    assert {"nba_data.api.app", "nba_data.db.session", "sqlalchemy.engine"} <= set(loaded)
    assert "nba_data.db.repositories.queries.teams" in loaded
    assert [name for name in loaded if _is_forbidden(name)] == []


@pytest.mark.unit
def test_the_installed_scikit_learn_fits_and_predicts_with_the_planned_estimators() -> None:
    """Installed wheels can still fail at import or fit (a binary mismatch). This runs
    the Stage 3 estimators on deterministic, clearly separable data in a fresh
    interpreter, so the test process itself never loads the ML stack.
    """

    result = _run_python(
        "import json\n"
        "import numpy as np\n"
        "from sklearn.calibration import CalibratedClassifierCV, calibration_curve\n"
        "from sklearn.ensemble import HistGradientBoostingClassifier\n"
        "from sklearn.linear_model import LogisticRegression\n"
        "from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score\n"
        "from sklearn.pipeline import make_pipeline\n"
        "from sklearn.preprocessing import StandardScaler\n"
        "rng = np.random.default_rng(0)\n"
        "x = rng.normal(size=(400, 4))\n"
        "y = (x @ np.array([1.5, -1.0, 0.5, 0.0]) + rng.normal(scale=0.5, size=400) > 0).astype(int)\n"
        "models = {\n"
        "    'logistic': make_pipeline(StandardScaler(), LogisticRegression()),\n"
        "    'boosting': HistGradientBoostingClassifier(max_iter=50, random_state=0),\n"
        "    'calibrated': CalibratedClassifierCV(LogisticRegression(), method='sigmoid', cv=3),\n"
        "}\n"
        "report = {}\n"
        "for name, model in models.items():\n"
        "    p = model.fit(x[:300], y[:300]).predict_proba(x[300:])[:, 1]\n"
        "    calibration_curve(y[300:], p, n_bins=5)\n"
        "    report[name] = {\n"
        "        'log_loss': log_loss(y[300:], p),\n"
        "        'brier': brier_score_loss(y[300:], p),\n"
        "        'auc': roc_auc_score(y[300:], p),\n"
        "        'in_unit_interval': bool(((p >= 0) & (p <= 1)).all()),\n"
        "    }\n"
        "print(json.dumps(report))\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.splitlines()[-1])

    assert set(report) == {"logistic", "boosting", "calibrated"}
    for name, metrics in report.items():
        assert metrics["in_unit_interval"], name
        # A strong linear signal: every model must clearly beat a coin flip.
        assert metrics["log_loss"] < math.log(2), (name, metrics)
        assert metrics["brier"] < 0.25, (name, metrics)
        assert metrics["auc"] > 0.8, (name, metrics)
