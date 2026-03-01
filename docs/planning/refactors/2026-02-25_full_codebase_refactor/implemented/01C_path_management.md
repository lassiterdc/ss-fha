# Work Chunk 01C: Path Management

**Phase**: 1C — Foundation (Path Dataclasses)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`CONTRIBUTING.md`](../../../../CONTRIBUTING.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 01A and 01B must be complete (`SSFHAConfig` importable).

---

## Task Understanding

### Requirements

Create `src/ss_fha/paths.py` containing dataclasses that provide organized, resolved file path management for the entire project. This replaces the ad-hoc path concatenation throughout `_old_code_to_refactor/__inputs.py` and the old scripts.

Paths are computed once from an `SSFHAConfig` and passed throughout the application, eliminating repeated `config.output_dir / "subdir" / "file"` constructions.

### Key Design Decisions

- **Dataclasses, not Pydantic models** — paths are derived/computed, not user-supplied. Plain `@dataclass` with `Path` fields is appropriate.
- **`ProjectPaths.from_config(config)` is the sole constructor** — never instantiate directly.
- **`ensure_dirs_exist()`** creates all output directories at workflow start, not lazily.
- **No defaults on `from_config()`** — the config object is the only argument; all paths are derived deterministically.

### Structure

```python
@dataclass
class ProjectPaths:
    # Root output dirs (no data_dir or project_dir — input paths live on the config model directly)
    output_dir: Path
    logs_dir: Path               # output_dir / "logs"

    # Workflow 1: Flood hazard
    flood_probs_dir: Path        # output_dir / "flood_probabilities"

    # Workflow 2: Uncertainty
    bootstrap_dir: Path          # output_dir / "bootstrap"
    bootstrap_samples_dir: Path  # bootstrap_dir / "samples"

    # Workflow 3: PPCCT
    ppcct_dir: Path              # output_dir / "ppcct"

    # Workflow 4: Flood risk
    flood_risk_dir: Path         # output_dir / "flood_risk"

    # Shared
    event_stats_dir: Path        # output_dir / "event_statistics"
    figures_dir: Path            # output_dir / "figures"

    @classmethod
    def from_config(cls, config: SSFHAConfig) -> "ProjectPaths": ...

    def ensure_dirs_exist(self) -> None: ...
```

**Design decision (confirmed 2026-02-25):** `ProjectPaths` manages *output* directories only. Input data paths (zarr files, shapefiles, CSVs) are stored as absolute `Path` fields directly on the config model (`config.triton_outputs.combined`, `config.event_data.sim_event_summaries`, etc.). This keeps the system flexible — input files can live anywhere on the filesystem, with no reliance on relative path conventions.

**Scratch directories:** Excluded from `ProjectPaths`. If a workflow step needs a scratch/temp location, use `tempfile.TemporaryDirectory` or add a dedicated named subdirectory at the time it is needed.

Check `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/paths.py` for patterns to adopt or improve upon (class names in that file are TRITON-SWMM_toolkit-specific and should not be copied directly).

### Success Criteria

- `ProjectPaths.from_config(config)` resolves all paths from a valid config without errors
- `ensure_dirs_exist()` creates all directories in a temporary path
- Tests pass

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/paths.py` — pattern reference
2. `_old_code_to_refactor/__inputs.py` — full inventory of output paths used in old scripts, to ensure `ProjectPaths` covers them all
3. `src/ss_fha/config/model.py` (from 01B) — understand `SSFHAConfig.output_dir` and `data_dir` fields

---

## Implementation Strategy

### Chosen Approach

`@dataclass` with a `from_config` classmethod. All fields are computed in `from_config` from the config's `output_dir` (defaulting to `project_dir / "outputs"` if not set in config). `ensure_dirs_exist()` iterates all `Path` fields that end in `_dir` using `dataclasses.fields()`.

### Alternatives Considered

- **Property-based computed paths on config model**: Rejected — mixes path resolution with Pydantic validation; dataclass is cleaner.
- **Passing raw config everywhere**: Rejected — leads to repetitive `config.output_dir / "bootstrap" / "samples"` chains and unclear ownership.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/paths.py` | `ProjectPaths` dataclass |
| `tests/test_paths.py` | Path resolution and directory creation tests |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/__init__.py` | Optionally re-export `ProjectPaths` |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| `output_dir` is `None` in config | `from_config` raises `ConfigurationError` — `output_dir` must be set. The loader sets it from the YAML parent dir if absent, so `None` should not reach `from_config` in practice. |
| `ensure_dirs_exist()` called with no write permission | Let `mkdir` raise `PermissionError` — fail fast per philosophy |
| Old scripts use paths not in `ProjectPaths` | Audit complete (2026-02-25). Scratch dirs excluded by design. Workflow-specific sub-dirs will be added in their respective chunks. |

---

## Validation Plan

```bash
# Path resolution test
pytest tests/test_paths.py::test_paths_from_config -v

# Directory creation test
pytest tests/test_paths.py::test_ensure_dirs_creates_directories -v

# Smoke test
python -c "
from pathlib import Path
from ss_fha.config.loader import load_config_from_dict
from ss_fha.paths import ProjectPaths
d = {'project_name': 'test', 'project_dir': '/tmp/ssfha_test', 'triton_outputs': {'compound': '/tmp/fake.zarr'}, 'event_data': {'sim_event_summaries': '/tmp/fake.csv'}, 'geospatial': {'watershed': '/tmp/fake.shp'}, 'execution': {'mode': 'local_concurrent'}}
cfg = load_config_from_dict(d)
paths = ProjectPaths.from_config(cfg)
print(paths.bootstrap_samples_dir)
"
```

---

## Documentation and Tracker Updates

- No tracking table changes needed (paths.py is a new file, not migrated from old code).
- If additional output paths are discovered during the `__inputs.py` audit, note them in `full_codebase_refactor.md`.

---

## Definition of Done

- [ ] `src/ss_fha/paths.py` implemented with `ProjectPaths` dataclass
- [ ] `from_config()` correctly derives all output paths from `config.output_dir`; raises `ConfigurationError` if `output_dir` is `None`
- [ ] `ensure_dirs_exist()` creates all `_dir` paths
- [ ] All Phase 1C tests pass
- [ ] **Move this document to `../implemented/` once all boxes above are checked**
