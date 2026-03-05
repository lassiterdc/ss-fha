"""Fixtures for old-code alignment tests.

Mocks ``__inputs`` in ``sys.modules`` so old-code scripts that use
``from __inputs import *`` can be imported without triggering directory
creation, path resolution, or other side effects from the real
``__inputs.py``.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest


@pytest.fixture(scope="session", autouse=True)
def mock_inputs_module():
    """Insert a mock ``__inputs`` module into ``sys.modules``.

    ``__inputs.py`` creates directories at import time and defines hundreds of
    path constants pointing to the developer's local filesystem. All old scripts
    use ``from __inputs import *``, making them non-importable without this mock.

    The mock provides ``MagicMock()`` for all attribute lookups, so functions
    that reference ``__inputs`` globals at call time get a harmless mock value.
    For functions that need a specific ``__inputs`` attribute at call time
    (e.g., a file path), individual tests must patch that attribute directly::

        mock_inputs_module.SOME_PATH = Path("/tmp/test")
    """
    mock = MagicMock()
    sys.modules["__inputs"] = mock
    yield mock
    del sys.modules["__inputs"]
