# Work Chunk 05: Visualization

**Phase**: 5 — Visualization
**Last edited**: 2026-02-25

---

## Before Proceeding

Review the following documents before making any edits to plans or writing any code:

- [`docs/planning/active/refactors/full_codebase_refactor/full_codebase_refactor.md`](../full_codebase_refactor.md) — master refactor plan; update it if any decisions made here affect the overall plan.
- [`.prompts/philosphy.md`](../../../../../.prompts/philosphy.md) — project development philosophy; all implementation decisions must align with it.

**Prerequisite**: Phases 1–4 complete (all workflows run end-to-end before visualization is added).

---

## Task Understanding

### Requirements

Migrate the plotting functions from `_old_code_to_refactor/__plotting.py` into domain-specific visualization modules. Add a `--figures` CLI command and optionally Snakemake rules for automated figure generation.

**Design decision (resolved)**: Visualization is decoupled from the main computation pipeline, but QAQC plots are an exception — they are generated as part of each runner script when `toggle_qaqc_plots=True` (the production default). Tests always set `toggle_qaqc_plots=False`.

**Files to create:**

1. `src/ss_fha/visualization/__init__.py`
2. `src/ss_fha/visualization/flood_maps.py` — spatial flood depth/probability maps
3. `src/ss_fha/visualization/probability_curves.py` — CDF, return period, depth-probability curves
4. `src/ss_fha/visualization/comparison_plots.py` — ensemble vs. design storm, event vs. flood return
5. `src/ss_fha/visualization/impact_plots.py` — feature impact, AOI analysis plots
6. `src/ss_fha/visualization/helpers.py` — colorbars, tick formatting, subplot labels, shared utilities

**CLI addition:**
- `ssfha plot config.yaml --figures all|flood_maps|probability_curves|comparison|impact`

**Config addition:**
- `toggle_qaqc_plots: bool` to `SSFHAConfig` — controls whether QAQC figures are generated as part of workflow runs (default in analysis is `True`; always `False` in tests)

### Key Design Decisions

- **Decouple from computation**: Visualization functions accept already-loaded xarray Datasets/DataArrays — no file I/O in visualization functions themselves.
- **`toggle_qaqc_plots`** integrates with runner scripts: each runner checks this toggle and optionally calls a QAQC plotting function after computation.
- Migration priority: prioritize plots that support QAQC and key paper figures; low-priority aesthetic plots can be migrated later.
- `__plotting.py` is 4,423 lines — audit it first and prioritize which functions to migrate vs. defer.

### Success Criteria

- Key QAQC plots generate from synthetic pipeline outputs without manual intervention
- `ssfha plot config.yaml --figures flood_maps` produces output figures
- `toggle_qaqc_plots=False` suppresses QAQC plot generation in runner scripts
- `__plotting.py` is fully superseded (tracking table updated to `COMPLETE`)

---

## Evidence from Codebase

Before implementing, inspect:

1. `_old_code_to_refactor/__plotting.py` — full audit of 4,423 lines; categorize functions by workflow (flood maps, probability curves, comparison, impact, misc)
2. `_old_code_to_refactor/b2d_sim_vs_obs_fld_ppct.py` — PPCCT plots (partially deferred from 03D)
3. `src/ss_fha/config/model.py` — add `toggle_qaqc_plots` field

---

## File-by-File Change Plan

### New Files

| File | Purpose |
|------|---------|
| `src/ss_fha/visualization/__init__.py` | Package stub |
| `src/ss_fha/visualization/flood_maps.py` | Spatial flood maps |
| `src/ss_fha/visualization/probability_curves.py` | CDF and return period plots |
| `src/ss_fha/visualization/comparison_plots.py` | Multi-method comparison plots |
| `src/ss_fha/visualization/impact_plots.py` | Feature impact plots |
| `src/ss_fha/visualization/helpers.py` | Shared plot utilities |

### Modified Files

| File | Change |
|------|--------|
| `src/ss_fha/config/model.py` | Add `toggle_qaqc_plots: bool` field |
| `src/ss_fha/cli.py` | Add `ssfha plot` command |
| All runner scripts (03A–03F) | Add QAQC plot calls guarded by `toggle_qaqc_plots` |
| `_old_code_to_refactor/__plotting.py` | Update refactoring status block |

---

## Risks and Edge Cases

| Risk | Mitigation |
|------|-----------|
| `__plotting.py` is 4,423 lines — scope is large | Prioritize migration; defer low-priority plots with `#TODO` comments |
| Matplotlib figure state is global — parallel runs may conflict | Use `plt.figure()` / `plt.close()` within each function; avoid `plt.show()` in runner contexts |
| QAQC plot files need sensible output paths | Use `ProjectPaths.figures_dir / workflow_name / plot_name.png`; never hardcode paths |

---

## Validation Plan

```bash
# QAQC plot generation (with toggle on)
ssfha run /tmp/ssfha_test/config_with_qaqc.yaml

# Figures CLI
ssfha plot /tmp/ssfha_test/config.yaml --figures flood_maps

# Verify figure files created
ls /tmp/ssfha_test/outputs/figures/
```

---

## Documentation and Tracker Updates

- Update `full_codebase_refactor.md` tracking table: `__plotting.py` → `COMPLETE` (or `PARTIAL` if some plots are intentionally deferred).
- Update `full_codebase_refactor.md` Phase 5 definition of done.

---

## Definition of Done

- [ ] All five `visualization/` modules implemented
- [ ] `toggle_qaqc_plots` config field added and wired into runner scripts
- [ ] `ssfha plot config.yaml --figures all` generates figures from pipeline outputs
- [ ] Key QAQC plots generate from synthetic test case outputs
- [ ] `toggle_qaqc_plots=False` confirmed to suppress plots (verified in tests)
- [ ] `__plotting.py` refactoring status block updated to `COMPLETE` (or `PARTIAL` with deferred list)
- [ ] `full_codebase_refactor.md` tracking table updated
- [ ] **Move this document to `implemented/` once all boxes above are checked**
