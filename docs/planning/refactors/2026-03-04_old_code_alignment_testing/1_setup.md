---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 1: Setup — Test Package + `__inputs` Mock

## Dependencies

**Upstream**: None — first phase.
**Downstream**: All other phases depend on this package and the mock fixture.

## Task Understanding

Create the `tests/test_old_code_alignment/` package and the `conftest.py` that makes old functions importable by mocking `sys.modules["__inputs"]`. Also investigate and fix the `assert_event_comparison_valid` bug found during audit.

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `tests/test_old_code_alignment/__init__.py` | Package marker |
| `tests/test_old_code_alignment/conftest.py` | `__inputs` mock fixture + any shared old-code import helpers |

### Modified Files

| File | Change |
|------|--------|
| `tests/utils_for_testing.py` | Implement or remove `assert_event_comparison_valid` (investigate first) |

## Implementation Notes

### `conftest.py` — `__inputs` mock

The mock must be inserted into `sys.modules` **before** any old-code module is imported in tests. Use a `pytest` session-scoped autouse fixture:

```python
import sys
import types
import pytest

@pytest.fixture(scope="session", autouse=True)
def mock_inputs_module():
    """Mock __inputs so old code modules can be imported without side effects.

    __inputs.py creates directories at import time and sets hundreds of path
    constants pointing to the developer's local filesystem. All old scripts
    use `from __inputs import *`, making them non-importable without this mock.

    The mock provides MagicMock() for all attribute lookups so functions that
    reference __inputs globals at call time get a harmless mock value.
    """
    from unittest.mock import MagicMock
    mock = MagicMock()
    sys.modules["__inputs"] = mock
    yield mock
    del sys.modules["__inputs"]
```

This mock makes every attribute lookup on `__inputs` return a `MagicMock` object. For functions that only reference `__inputs` globals at module load (not at call time), this is sufficient. For functions that read a specific `__inputs` value at call time (e.g., a file path), individual test functions must patch that attribute directly.

### `assert_event_comparison_valid` bug

Before implementing anything, read `tests/test_event_stats_workflow.py` to understand what `assert_event_comparison_valid` is expected to validate, then implement it in `tests/utils_for_testing.py`. The function likely validates the structure of the event comparison output zarr/netcdf (dimensions, variable names, expected columns). If the implementation is unclear, investigate `src/ss_fha/analysis/event_comparison.py` outputs.

## Validation Plan

```bash
# Package is importable and mock fixture works
conda run -n ss-fha pytest tests/test_old_code_alignment/ -v

# No regressions
conda run -n ss-fha pytest tests/ -v
```

## Definition of Done

- [ ] `tests/test_old_code_alignment/__init__.py` created
- [ ] `tests/test_old_code_alignment/conftest.py` with `mock_inputs_module` session fixture
- [ ] `assert_event_comparison_valid` investigated, implemented or import removed
- [ ] `pytest tests/test_old_code_alignment/ -v` passes (no tests yet, but package is importable)
- [ ] `pytest tests/ -v` passes (no regressions)
- [ ] Move this doc to `implemented/`

## Lessons Learned

_(fill in after implementation)_
