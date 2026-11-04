"""numpy for this package, opaque to mypy.

numpy 2.5's stubs use syntax newer than `[tool.mypy] python_version = "3.11"`,
and mypy stops at them. Importing numpy here keeps that out of the type check.
Replace this module with plain imports once that setting moves to 3.12.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    np: Any = None
    Array: TypeAlias = Any
else:
    import numpy as np

    Array = np.ndarray

__all__ = ["Array", "np"]
