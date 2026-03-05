"""Fixtures and module-level mocks for old-code alignment tests.

Mocks ``__inputs`` and ``local.__inputs`` in ``sys.modules`` so old-code
scripts that use ``from __inputs import *`` or ``from local.__inputs import
...`` can be imported without triggering directory creation, path resolution,
or other side effects from the real ``__inputs.py``.

The mock is installed at **module level** (not inside a fixture) because
old-code imports happen at collection time — before any fixture runs.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Module-level mock: must execute before any test module imports __utils
# ---------------------------------------------------------------------------
_mock_inputs = MagicMock()

# Also add _old_code_to_refactor to sys.path so `import __utils` works
_old_code_dir = str(Path(__file__).parents[2] / "_old_code_to_refactor")
if _old_code_dir not in sys.path:
    sys.path.insert(0, _old_code_dir)

# Mock both import paths: `from __inputs import *` and `from local.__inputs import ...`
_local_mock = types.ModuleType("local")
_local_mock.__inputs = _mock_inputs  # type: ignore[attr-defined]
sys.modules["__inputs"] = _mock_inputs
sys.modules["local"] = _local_mock
sys.modules["local.__inputs"] = _mock_inputs
