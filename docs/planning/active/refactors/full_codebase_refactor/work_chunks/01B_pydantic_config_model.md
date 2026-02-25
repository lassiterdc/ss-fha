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

1. `src/ss_fha/config/model.py` — Pydantic v2 config models: `SystemConfig` (shared geographic context) and a discriminated-union analysis config (`SsfhaConfig | BdsConfig`) rooted at `SSFHAConfig`. Replaces `_old_code_to_refactor/__inputs.py` as the canonical source of all user-configurable inputs.

2. `src/ss_fha/config/loader.py` — YAML loading with template-placeholder support:
   - `load_system_config(yaml_path: Path) -> SystemConfig`
   - `load_config(yaml_path: Path) -> SSFHAConfig` — loads the analysis YAML; if `study_area_config` is present, loads and merges the referenced `system.yaml` automatically
   - `load_config_from_dict(d: dict) -> SSFHAConfig`

**Note**: `src/ss_fha/examples/config_templates/norfolk_default.yaml` is owned by work chunk 01G, not this chunk. Do not create it here.

### Key Design Decisions from Master Plan

- **No defaults for case-study-specific parameters** (per philosophy.md "Most function arguments should not have defaults"). EPSG, study area bounds, etc. must be explicit.
- **`n_years_synthesized` is a required top-level field on `SSFHAConfig`** — it is the total number of synthetic years in the weather model run (e.g., 1000 for Norfolk), including years that produced no events. It is NOT derived from the data: the time series only contains years with ≥1 event (954 for Norfolk), so reading `len(ds.year)` would give the wrong value. Users must supply this explicitly. It is the denominator for all return period calculations; a wrong value silently biases every result. There is no default.
- **`n_years_observed` is a required field when `toggle_ppcct: true`** — it is the total number of years of observed record, including any years with no events. For Norfolk, all 18 observed years have ≥1 event, so `n_years_observed = 18 = len(obs_ds.year)`. However, other case studies may have observed years with no events, so this must be explicit for the same reason as `n_years_synthesized`. It is the denominator for observed return period calculations in PPCCT. There is no default.
- **`serial` execution mode is removed** — only `local_concurrent` and `slurm`. Snakemake handles serialization via available resources.
- **FHA comparison design (resolved)**: Each FHA approach is its own `SSFHAConfig` with a unique `fha_id` and `fha_approach` (`ssfha`, `bds`). The primary config optionally includes `alt_fha_analyses: list[Path]` pointing to alternative configs. `TritonOutputsConfig` holds the `combined` path (primary simulation type) and the optional `observed` path for PPCCT — the surge-only/rain-only variants are separate FHA configs, not fields on a single `TritonOutputsConfig`. See the master plan "Multi-FHA Analysis Design" section.
- **MCDS is a toggle, not an `fha_approach`**: Because MCDS reuses the stochastic ensemble directly (no separate model inputs), it is implemented as `toggle_mcds: bool` on the primary SSFHA combined config rather than as a standalone FHA approach. A `@model_validator` must raise `ConfigurationError` if `toggle_mcds=True` when `fha_approach != "ssfha"`. See work chunk 00 Decision 3.
- **`MeteorologicalConfig` (resolved)**: Removed entirely. Design storm creation is out of scope. Event statistics uses tide gage data and empirical return period CSVs, but these are referenced directly via `EventDataConfig`, not via a separate `MeteorologicalConfig`.

### Config model hierarchy

Two top-level models — `SystemConfig` (geographic context, shared across analyses) and `SSFHAConfig` (a discriminated union on `fha_approach`):

```
SystemConfig                          # system.yaml — fixed geographic context
├── crs_epsg: int                     # required; no default
└── GeospatialConfig                  # all geospatial file paths
    ├── watershed: Path
    ├── roads: Path | None
    ├── sidewalks: Path | None
    ├── buildings: Path | None
    ├── parcels: Path | None
    └── fema_flood_raster: Path | None

SSFHAConfig = Annotated[              # analysis_*.yaml — discriminated union
    SsfhaConfig | BdsConfig,
    Field(discriminator="fha_approach")
]

SsfhaConfig (fha_approach="ssfha")
├── fha_id: str
├── study_area_config: Path | None    # optional ref to system.yaml; loader merges automatically
├── n_years_synthesized: int          # required; no default
├── return_periods: list[int]
├── toggle_mcds: bool
├── toggle_ppcct: bool
├── toggle_flood_risk: bool
├── toggle_design_comparison: bool
├── alt_fha_analyses: list[Path]      # other analysis YAMLs (bds, surgeonly, etc.)
├── TritonOutputsConfig               # paths to TRITON zarr outputs
│   ├── combined: Path                # primary (combined rain+surge) zarr
│   └── observed: Path | None        # observed events zarr (required if toggle_ppcct)
├── EventDataConfig                   # event summary CSVs, timeseries dir
├── PPCCTConfig | None                # required if toggle_ppcct
├── FloodRiskConfig | None            # required if toggle_flood_risk
└── ExecutionConfig
    └── SlurmConfig | None            # required if mode == "slurm"

BdsConfig (fha_approach="bds")
├── fha_id: str
├── study_area_config: Path | None
├── return_periods: list[int]
├── toggle_uncertainty: bool
├── toggle_ppcct: bool
├── toggle_flood_risk: bool
├── design_storm_output: Path         # scalar — one zarr per BDS config
├── design_storm_timeseries: Path     # scalar — one timeseries per BDS config
├── PPCCTConfig | None
├── FloodRiskConfig | None
└── ExecutionConfig
    └── SlurmConfig | None
```

**Discriminator pattern**: `fha_approach: Literal["ssfha"]` on `SsfhaConfig` and `fha_approach: Literal["bds"]` on `BdsConfig`. Pydantic v2 `Annotated[..., Field(discriminator="fha_approach")]` selects the correct model at parse time — no custom validator needed.

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

Implement `SystemConfig` and a discriminated-union `SSFHAConfig` (`SsfhaConfig | BdsConfig`) as Pydantic v2 `BaseModel`s. Use `@model_validator(mode='after')` for cross-field toggle validation within each analysis config subtype. Load YAML with PyYAML in `loader.py`, fill `{{placeholder}}` template strings before Pydantic parsing. When `study_area_config` is present in the analysis YAML, the loader reads the referenced `system.yaml` and merges its fields into the analysis dict before parsing.

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
| `src/ss_fha/config/model.py` | `SystemConfig`, `SsfhaConfig`, `BdsConfig`, `SSFHAConfig` discriminated union, all sub-models |
| `src/ss_fha/config/loader.py` | `load_system_config()`, `load_config()`, `load_config_from_dict()`, template filling, system-merge logic |

**Note**: `src/ss_fha/examples/__init__.py` and `src/ss_fha/examples/config_templates/norfolk_default.yaml` (a distributable template with `{{placeholder}}` syntax — distinct from the filled-in YAMLs in `cases/norfolk_ssfha_comparison/` created in chunk 00) are owned by work chunk 01G. Do not create them here.

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
| `study_area_config` merge order — analysis fields must win over system defaults | Deep-merge system dict first, then overlay analysis dict; never let system values overwrite analysis-level values |
| Discriminated union parse failure gives poor error messages by default | Pydantic v2 surfaces the discriminator key mismatch clearly; verify manually with an invalid `fha_approach` in a test |

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

# Norfolk case study YAMLs round-trip (parametrized over all analysis_*.yaml files)
pytest tests/test_config.py::test_norfolk_case_yamls_load -v

# Smoke test: minimal SsfhaConfig (no system.yaml — geospatial passed inline for this test only)
python -c "
from ss_fha.config.loader import load_config_from_dict
d = {
    'fha_id': 'test_ssfha', 'fha_approach': 'ssfha',
    'n_years_synthesized': 1000, 'return_periods': [1, 2, 10, 100],
    'toggle_mcds': False, 'toggle_ppcct': False,
    'toggle_flood_risk': False, 'toggle_design_comparison': False,
    'triton_outputs': {'combined': '/tmp/fake.zarr'},
    'event_data': {'sim_event_summaries': '/tmp/fake.csv'},
    'execution': {'mode': 'local_concurrent'},
}
cfg = load_config_from_dict(d)
print(cfg.fha_id)
"

# Smoke test: minimal BdsConfig
python -c "
from ss_fha.config.loader import load_config_from_dict
d = {
    'fha_id': 'test_bds', 'fha_approach': 'bds',
    'return_periods': [1, 2, 10, 100],
    'toggle_uncertainty': False, 'toggle_ppcct': False, 'toggle_flood_risk': False,
    'design_storm_output': '/tmp/fake_bds.zarr',
    'design_storm_timeseries': '/tmp/fake_ts.csv',
    'execution': {'mode': 'local_concurrent'},
}
cfg = load_config_from_dict(d)
print(cfg.fha_id)
"

# Critical smoke test: all Norfolk case study YAMLs parse without error
# These were written provisionally in chunk 00; this is their first real validation against SSFHAConfig
for yaml in cases/norfolk_ssfha_comparison/analysis_*.yaml; do
    python -c "
from ss_fha.config.loader import load_config
cfg = load_config('$yaml')
print(f'OK: $yaml -> {cfg.fha_id}')
"
done

# Critical smoke test: system.yaml parses as SystemConfig
python -c "
from ss_fha.config.loader import load_system_config
cfg = load_system_config('cases/norfolk_ssfha_comparison/system.yaml')
print(f'OK: system.yaml -> crs_epsg={cfg.crs_epsg}')
"
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__inputs.py` moves from `PARTIAL` to reflect config model migration.
- If the multi-FHA-config design question is resolved during implementation, update `full_codebase_refactor.md` with the decision.

---

## Definition of Done

- [ ] `src/ss_fha/config/model.py` implemented: `SystemConfig`, `SsfhaConfig`, `BdsConfig`, `SSFHAConfig` discriminated union, all sub-models
- [ ] `src/ss_fha/config/loader.py` implemented: `load_system_config`, `load_config`, `load_config_from_dict`, template filling, system-merge logic
- [ ] `GeospatialConfig` is on `SystemConfig`, not on analysis config models
- [ ] `study_area_config: Path | None` field on both `SsfhaConfig` and `BdsConfig`; `load_config` merges system YAML automatically when present
- [ ] `SSFHAConfig` is a Pydantic v2 discriminated union on `fha_approach` (`SsfhaConfig | BdsConfig`)
- [ ] Toggle validation accumulates errors before raising
- [ ] `serial` execution mode removed from `ExecutionConfig`
- [ ] No case-study-specific defaults in the model (EPSG, etc. are required fields)
- [ ] `TritonOutputsConfig` uses field name `combined` (not `compound`) for the primary simulation zarr path
- [ ] `fha_approach` is `Literal["ssfha", "bds"]` — `mcds` is NOT a separate approach; MCDS is `toggle_mcds: bool` on `SsfhaConfig`
- [ ] `toggle_mcds` validator raises `ConfigurationError` if `toggle_mcds=True` and `fha_approach != "ssfha"`
- [ ] All Phase 1B tests pass (both SsfhaConfig and BdsConfig smoke tests pass)
- [ ] Refactoring status block updated in `_old_code_to_refactor/__inputs.py`
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] Each YAML in `cases/norfolk_ssfha_comparison/` loads without error via `load_config` (smoke test — these YAMLs were written provisionally in chunk 00 and must be validated here)
- [ ] **Move this document to `implemented/` once all boxes above are checked**
