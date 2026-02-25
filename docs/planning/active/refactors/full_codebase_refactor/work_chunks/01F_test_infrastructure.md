# Work Chunk 01F: Test Infrastructure

**Phase**: 1F — Foundation (Test Infrastructure)
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Work chunks 01A–01E complete. Test infrastructure requires all Phase 1 modules to be importable.

---

## Task Understanding

### Requirements

Build the test scaffolding that all future phases depend on. This chunk produces no production logic — only fixtures, builders, and helpers.

**Files to create:**

1. `tests/conftest.py` — shared pytest fixtures:
   - `tmp_project_dir` — temporary directory with expected project structure
   - `minimal_config` — smallest valid `SSFHAConfig` using synthetic on-disk data (Workflow 1 only)
   - `full_config` — `SSFHAConfig` with all toggles enabled using synthetic data
   - `synthetic_flood_dataset` — small xarray Dataset mimicking TRITON zarr output

2. `tests/fixtures/__init__.py`

3. `tests/fixtures/test_case_builder.py` — synthetic data generators:
   - `build_synthetic_triton_output(n_events: int, nx: int, ny: int) -> xr.Dataset`
   - `build_synthetic_observed_output(n_events: int, nx: int, ny: int) -> xr.Dataset`
   - `build_synthetic_event_summaries(n_events: int) -> pd.DataFrame`
   - `build_synthetic_watershed(nx: int, ny: int, crs_epsg: int) -> gpd.GeoDataFrame`
   - `build_minimal_test_case(tmp_path: Path) -> SSFHAConfig` — creates config + all synthetic data files on disk, returns ready-to-use config

4. `tests/fixtures/test_case_catalog.py`:
   - `retrieve_norfolk_case_study(start_from_scratch: bool)` — downloads from HydroShare (integration test only, marked `@pytest.mark.slow`)

5. `tests/utils_for_testing.py` — platform detection and assertion helpers:
   - `uses_slurm() -> bool`
   - `on_uva_hpc() -> bool`
   - `skip_if_no_slurm` — pytest mark
   - `skip_if_no_hydroshare` — pytest mark
   - `assert_zarr_valid(path: Path, expected_vars: list[str] | None) -> None`
   - `assert_flood_probs_valid(ds: xr.Dataset) -> None`

### Key Design Decisions

- **Synthetic data dimensions**: 10×10 grid, 10 simulation events, 5 observed events, 5 bootstrap samples. These small sizes keep CI fast (<5 min).
- **All arguments explicit** (no defaults) in builder functions — the caller decides dimensions.
- **No `DEFAULT_CRS_EPSG`** in builders — pass CRS explicitly.
- **TRITON output structure**: Before writing `build_synthetic_triton_output`, inspect the real TRITON zarr output schema from `/home/dcl3nd/dev/TRITON-SWMM_toolkit` to ensure correct variable names, dimension names, and coordinate dtypes. The synthetic data must be structurally identical to real data so tests validate real-world compatibility.
- **`build_minimal_test_case`** writes all synthetic data files to disk and returns a fully valid `SSFHAConfig` — this is the primary fixture for integration tests.
- **End-to-end test scaffolding**: The master plan notes that end-to-end tests must reproduce existing results on a test case before HPC testing. `build_minimal_test_case` is the foundation for this. Ensure the builder is designed so that known-good reference outputs can be checked against.

### Success Criteria

- `pytest tests/test_config.py::test_synthetic_test_case_builds` passes
- `minimal_config` fixture yields a valid, file-backed `SSFHAConfig`
- `build_synthetic_triton_output` produces an xarray Dataset with correct variable and dimension names matching real TRITON output

---

## Evidence from Codebase

Before implementing, inspect:

1. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/fixtures/test_case_builder.py` — pattern to adopt
2. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/fixtures/test_case_catalog.py` — pattern for case catalog
3. `/home/dcl3nd/dev/TRITON-SWMM_toolkit/tests/utils_for_testing.py` — platform detection and assertion helper patterns
4. A real TRITON zarr output (if accessible) — to determine correct schema for `build_synthetic_triton_output`
5. `src/ss_fha/config/model.py` (01B) — to know all fields `build_minimal_test_case` must populate
6. `src/ss_fha/io/zarr_io.py` (01D) — use these for writing synthetic files to disk in test builders

---

## Implementation Strategy

### Chosen Approach

Mirror TRITON-SWMM_toolkit test infrastructure, adapting for ss_fha's data schemas. All builders are pure functions returning in-memory objects or writing to a caller-supplied `tmp_path`. Fixtures in `conftest.py` call the builders.

### Alternatives Considered

- **Use real HydroShare data for all tests**: Rejected — slow, requires network, violates "tests must be runnable offline" requirement.
- **Parameterize test dimensions via config**: Rejected — adds complexity; fixed small sizes are fine for unit/integration tests.

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `tests/conftest.py` | Shared fixtures (`tmp_project_dir`, `minimal_config`, `full_config`, `synthetic_flood_dataset`) |
| `tests/fixtures/__init__.py` | Package stub |
| `tests/fixtures/test_case_builder.py` | Synthetic data generators |
| `tests/fixtures/test_case_catalog.py` | HydroShare integration helper (slow, marked accordingly) |
| `tests/utils_for_testing.py` | Platform detection, assertion helpers |

### Modified Files

| File | Change |
|------|--------|
| `tests/test_config.py` | Add `test_synthetic_test_case_builds` |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| TRITON zarr schema changes between versions | Document the schema version assumed by builders in a comment; add an assertion in `assert_zarr_valid` |
| `retrieve_norfolk_case_study` may fail if HydroShare is down | Mark with `@pytest.mark.slow` and `skip_if_no_hydroshare`; never run in CI by default |
| `build_minimal_test_case` must write zarr to disk (not just in-memory) | Use `zarr_io.write_zarr()` from 01D; this tests the I/O layer too |
| Synthetic GeoDataFrame CRS must match the CRS used in `create_mask_from_shapefile` | Pass the same `crs_epsg` through all layers; never hardcode in builders |

---

## Validation Plan

```bash
# Synthetic test case builds without error
pytest tests/test_config.py::test_synthetic_test_case_builds -v

# Fixtures are usable (run all Phase 1 tests)
pytest tests/test_config.py tests/test_paths.py tests/test_io.py -v

# Full test suite (Phase 1 complete)
pytest tests/ -v --ignore=tests/test_UVA_end_to_end.py -k "not slow"
```

---

## Documentation and Tracker Updates

- No tracking table changes (new files only).
- If TRITON zarr schema is documented anywhere, reference it in a comment in `test_case_builder.py`.

---

## Definition of Done

- [ ] `tests/conftest.py` with all four fixtures
- [ ] `tests/fixtures/test_case_builder.py` with all builder functions (no default arguments)
- [ ] `tests/fixtures/test_case_catalog.py` with HydroShare helper (marked `@pytest.mark.slow`)
- [ ] `tests/utils_for_testing.py` with platform detection and assertion helpers
- [ ] `build_synthetic_triton_output` produces schema-compatible data (verified against real TRITON output)
- [ ] `build_minimal_test_case` writes all files to disk and returns a valid `SSFHAConfig`
- [ ] `test_synthetic_test_case_builds` passes
- [ ] All Phase 1 tests pass: `pytest tests/ -k "not slow"`
- [ ] **Move this document to `implemented/` once all boxes above are checked**
