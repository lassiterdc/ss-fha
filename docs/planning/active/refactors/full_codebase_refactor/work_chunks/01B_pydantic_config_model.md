# Work Chunk 01B: Pydantic Configuration Model and YAML Loader

**Phase**: 1B — Foundation (Pydantic Config Model)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunk 01A must be complete (`ss_fha.exceptions` and `ss_fha.config.defaults` importable).

---

## Task Understanding

### Requirements

1. `src/ss_fha/config/model.py` — Pydantic v2 config model (`SSFHAConfig`) that replaces `_old_code_to_refactor/__inputs.py` as the canonical source of all user-configurable inputs.

2. `src/ss_fha/config/loader.py` — YAML loading with template-placeholder support:
   - `load_config(yaml_path: Path) -> SSFHAConfig`
   - `load_config_from_dict(d: dict) -> SSFHAConfig`

3. `src/ss_fha/examples/config_templates/norfolk_default.yaml` — Reference YAML template for the Norfolk case study (with `{{placeholder}}` syntax for paths that must be filled at runtime).

### Key Design Decisions from Master Plan

- **No defaults for case-study-specific parameters** (per philosophy.md "Most function arguments should not have defaults"). EPSG, study area bounds, etc. must be explicit.
- **`synthetic_years` is NOT a default** — it is derived from the weather index data, not user-configured.
- **`serial` execution mode is removed** — only `local_concurrent` and `slurm`. Snakemake handles serialization via available resources.
- **FHA comparison design (resolved)**: Each FHA approach is its own `SSFHAConfig` with a unique `fha_id` and `fha_approach` (`ssfha`, `bds`, `mcds`). The primary config optionally includes `alt_fha_analyses: list[Path]` pointing to alternative configs. `TritonOutputsConfig` only holds the `compound` path and the optional `observed` path for PPCCT — the surge-only/rain-only variants are separate FHA configs, not fields on a single `TritonOutputsConfig`. See the master plan "Multi-FHA Analysis Design" section.
- **`MeteorologicalConfig` (resolved)**: Removed entirely. Design storm creation is out of scope. Event statistics uses tide gage data and empirical return period CSVs, but these are referenced directly via `EventDataConfig`, not via a separate `MeteorologicalConfig`.

### Sub-models to implement

```
SSFHAConfig
├── TritonOutputsConfig       # paths to TRITON zarr outputs
├── EventDataConfig           # event summary CSVs, timeseries dir
├── GeospatialConfig          # watershed + optional AOIs, shapefiles
├── PPCCTConfig               # (optional) PPCCT-specific params
├── FloodRiskConfig           # (optional) roads, buildings, parcels
└── ExecutionConfig
    └── SlurmConfig           # (optional) SLURM resource params
```

### Toggle Validation

When `toggle_ppcct=True`, a `@model_validator` must verify:
- `ppcct` config section is present
- `triton_outputs.observed` path is set
- `event_data.obs_event_summaries` path is set

Similar validators for `toggle_flood_risk` and `toggle_design_comparison`. Errors must accumulate (do not raise on first failure) — use Pydantic v2's `model_validator(mode='after')` with a list collector and raise `ss_fha.exceptions.ConfigurationError` (or Pydantic's own `ValueError` collected by Pydantic) at the end.

### Success Criteria

- Minimal valid YAML (Workflow 1 only) loads without error
- Toggle validation catches missing dependencies with clear messages
- Relative paths resolve against `project_dir`
- All tests in `tests/test_config.py` for Phase 1B pass

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/src/TRITON_SWMM_toolkit/config/analysis.py` — Pydantic config pattern and toggle validation approach
2. `_old_code_to_refactor/__inputs.py` — full inventory of configurable fields to capture
3. `src/ss_fha/config/defaults.py` (from 01A) — import defaults from here
4. `src/ss_fha/exceptions.py` (from 01A) — use `ConfigurationError` for validation failures

---

## Implementation Strategy

### Chosen Approach

Implement `SSFHAConfig` as a Pydantic v2 `BaseModel` with nested sub-models. Use `@model_validator(mode='after')` for cross-field toggle validation. Load YAML with PyYAML in `loader.py`, fill `{{placeholder}}` template strings before Pydantic parsing.

### Alternatives Considered

- **Pydantic v1 style**: Rejected — environment uses Pydantic v2; use v2 API (`model_validator`, `field_validator`).
- **dataclasses + manual validation**: Rejected — Pydantic provides better error messages and JSON schema generation for free.

### Trade-offs

- Pydantic v2 validators are strict about import paths; be careful with forward references and `model_rebuild()` if circular refs arise.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/config/model.py` | Full Pydantic config hierarchy (`SSFHAConfig` + sub-models) |
| `src/ss_fha/config/loader.py` | `load_config()`, `load_config_from_dict()`, template filling |
| `src/ss_fha/examples/__init__.py` | Package stub |
| `src/ss_fha/examples/config_templates/norfolk_default.yaml` | Reference YAML template for Norfolk |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/config/__init__.py` | Re-export `SSFHAConfig`, `load_config` for convenience |
| `tests/test_config.py` | Add Phase 1B tests (see Validation Plan) |
| `_old_code_to_refactor/__inputs.py` | Update refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| Pydantic v2 `model_validator` accumulation pattern differs from v1 | Test accumulation explicitly: one validator that collects all issues, raises once |
| `Path` fields: Pydantic coerces strings to `Path` but doesn't check existence | Existence checks belong in `validation.py` (01E), not the config model |
| Template placeholder filling with `{{}}` — clashes with YAML or Pydantic | Use simple `str.replace()` on raw YAML string before PyYAML parsing; test with a minimal template |
| `ValidationError` name collision with Pydantic | Use fully qualified name or alias: `from ss_fha.exceptions import ValidationError as SSFHAValidationError` |

---

## Validation Plan

```bash
# Minimal config load (Workflow 1 only)
pytest tests/test_config.py::test_minimal_config_loads -v

# Toggle dependency validation
pytest tests/test_config.py::test_toggle_dependencies -v

# Missing required fields
pytest tests/test_config.py::test_config_validates_required_fields -v

# Path resolution (relative → absolute via project_dir)
pytest tests/test_config.py::test_path_resolution -v

# Defaults applied for optional fields
pytest tests/test_config.py::test_defaults_applied -v

# Workflow 1 only minimal inputs
pytest tests/test_config.py::test_workflow1_only_minimal_inputs -v

# Smoke test: load the norfolk_default.yaml template (with placeholder filling)
python -c "
from ss_fha.config.loader import load_config_from_dict
d = {'project_name': 'test', 'project_dir': '/tmp/test', 'triton_outputs': {'compound': '/tmp/fake.zarr'}, 'event_data': {'sim_event_summaries': '/tmp/fake.csv'}, 'geospatial': {'watershed': '/tmp/fake.shp'}, 'execution': {'mode': 'local_concurrent'}}
cfg = load_config_from_dict(d)
print(cfg.project_name)
"
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__inputs.py` moves from `PARTIAL` to reflect config model migration.
- If the multi-FHA-config design question is resolved during implementation, update `full_codebase_refactor.md` with the decision.

---

## Definition of Done

- [ ] `src/ss_fha/config/model.py` implemented with all sub-models
- [ ] `src/ss_fha/config/loader.py` implemented (`load_config`, `load_config_from_dict`, template filling)
- [ ] `src/ss_fha/examples/config_templates/norfolk_default.yaml` created
- [ ] Toggle validation accumulates errors before raising
- [ ] `serial` execution mode removed from `ExecutionConfig`
- [ ] No case-study-specific defaults in the model (EPSG, etc. are required fields)
- [ ] All Phase 1B tests pass
- [ ] Refactoring status block updated in `_old_code_to_refactor/__inputs.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `implemented/` once all boxes above are checked**
