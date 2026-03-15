---
impact: Medium
urgency: Low
loe: Low
risk: Low
priority: 1.80
priority-label: "Solid investment"
created: 2026-03-14
description: "Phase 4 — test speed convention: @pytest.mark.slow, pyproject.toml config, retroactive marking of slow tests"
master: docs/planning/refactors/se_audit_remediation/master.md
dependencies:
  - docs/planning/refactors/se_audit_remediation/3_conventions_and_infrastructure.md  # test changes from Phase 3
---

# Phase 4: Test Speed Convention

## Dependencies

**Upstream**: Phase 3 (test refactoring may create new tests worth marking).
**Downstream**: None.

## Task Understanding

### Requirements

Address audit findings Section 5 item 5 (test speed convention). Establish a two-tier test convention so `pytest tests/` runs fast by default and `pytest tests/ --runslow` includes integration tests.

### Success Criteria

- `@pytest.mark.slow` mark registered in `pyproject.toml`
- Slow tests deselected by default (via `addopts` or marker-based filtering)
- All tests that write to disk, invoke subprocesses, or take > 2 seconds are marked `slow`
- `pytest tests/` completes in under 30 seconds (excluding slow tests)
- `pytest tests/ --runslow` runs everything

## File-by-File Change Plan

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add to `[tool.pytest.ini_options]`: `markers = ["slow: marks tests as slow (deselect with '-m not slow')", "slurm: marks tests requiring SLURM", "hydroshare: marks tests requiring HydroShare access"]`. Add `addopts = "-m 'not slow'"` so slow tests are excluded by default. |
| `tests/conftest.py` | Add `--runslow` CLI option: `def pytest_addoption(parser): parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")`. Add a hook that removes the `-m 'not slow'` filter when `--runslow` is passed. |
| `tests/test_event_stats_workflow.py` | Mark `test_runner_cli_end_to_end` with `@pytest.mark.slow` (subprocess invocation + zarr writes). |
| `tests/test_flood_hazard_workflow.py` | Mark integration tests that write zarr to disk with `@pytest.mark.slow`. |
| `tests/test_bootstrap_workflow.py` | Mark integration tests with `@pytest.mark.slow` (if this file exists — verify). |
| `tests/test_old_code_alignment/*.py` | Mark all alignment tests with `@pytest.mark.slow` — they import old code and run comparison logic. |

## Implementation Notes

### `--runslow` mechanism

The `addopts = "-m 'not slow'"` in `pyproject.toml` applies the marker filter by default. When `--runslow` is passed, the conftest hook should override this by clearing the marker expression:

```python
def pytest_addoption(parser):
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")

def pytest_configure(config):
    if config.getoption("runslow"):
        # Override the default -m filter to run everything
        config.option.markexpr = ""
```

### Identifying slow tests

Search for tests that:
- Use `subprocess.run` or `subprocess.call`
- Write to `tmp_path` using zarr/netcdf
- Import from `_old_code_to_refactor`
- Use fixtures that create large synthetic datasets

Run `pytest tests/ -v --durations=0` to get timing data for all tests — any over 2 seconds should be marked.

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| `addopts` override interferes with CI | CI config should use `pytest tests/ --runslow` explicitly. Document this in `CONTRIBUTING.md`. |
| Developers forget to add `@pytest.mark.slow` to new slow tests | Add a note to `CONTRIBUTING.md` about the convention. The existing `skip_if_no_slurm` pattern is analogous — extend the same convention. |

## Validation Plan

```bash
# Fast tests only (default)
conda run -n ss-fha pytest tests/ -v
# Should complete in < 30 seconds, should skip slow tests

# All tests including slow
conda run -n ss-fha pytest tests/ -v --runslow
# Should run everything

# Verify timing
conda run -n ss-fha pytest tests/ -v --runslow --durations=10
```

## Documentation and Tracker Updates

| Doc | Update |
|-----|--------|
| `CONTRIBUTING.md` | Add section on test speed convention: when to use `@pytest.mark.slow`, how to run slow tests, CI expectations. |

## Definition of Done

- [ ] `@pytest.mark.slow` registered in `pyproject.toml`
- [ ] `addopts` deselects slow tests by default
- [ ] `--runslow` option implemented in conftest
- [ ] All integration tests and alignment tests marked `@pytest.mark.slow`
- [ ] `pytest tests/` completes in < 30 seconds
- [ ] `pytest tests/ --runslow` runs all tests and passes
- [ ] `CONTRIBUTING.md` updated with test speed convention
- [ ] If any performance or memory risks were surfaced, entries added to `docs/planning/bugs/tech_debt_known_risks.md`
- [ ] Move this doc to `implemented/`
