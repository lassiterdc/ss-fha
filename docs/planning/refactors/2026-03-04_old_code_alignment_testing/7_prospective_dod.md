---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 7: Prospective — DoD Gate on 03D Onward

## Dependencies

**Upstream**: Phase 1 must be complete. Phases 2–6 should be complete or substantially underway.
**Downstream**: Unblocks 03D and all subsequent work chunks.

## Task Understanding

Add the alignment DoD checkbox to all incomplete work chunk plans (03D onward). Also update `full_codebase_refactor.md` to document this as a hard requirement going forward.

## Files to Modify

### `docs/planning/refactors/2026-02-25_full_codebase_refactor/work_chunks/03D_workflow3_ppcct.md`

Add to Definition of Done:
```markdown
- [ ] Old-code alignment test: for each core computation function (`calc_emp_vs_fit_corr`, `interpolate_quantile_function`, `interpolate_cdf`, multiple-testing correction logic), either:
  - A direct import test in `tests/test_old_code_alignment/test_align_ppcct.py`, OR
  - A committed notebook in `_old_code_to_refactor/demonstrating_functional_alignment/` with explanation of why direct import was not feasible
```

### All other incomplete work chunk `.md` files (03E, 03F, 04–06 when created)

When each work chunk plan is written, the DoD template must include:
```markdown
- [ ] Old-code alignment test: direct import test in `tests/test_old_code_alignment/` or committed notebook in `_old_code_to_refactor/demonstrating_functional_alignment/` for all core computation functions ported from old code. No chunk is marked complete without this gate.
```

### `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`

Update the Requirements section (item 8) to explicitly state:
- Direct import into pytest is strongly preferred
- Notebook fallback required when direct import is not feasible (with explanation in notebook)
- All alignment tests/notebooks live in designated directories
- No work chunk (03D onward) is marked complete without this gate

Also add to the Workflow Phases section that the `refactor-plan` skill enforces this gate.

## Validation Plan

This phase is documentation-only — no code changes. Validation is manual review of updated files.

## Definition of Done

- [ ] `03D_workflow3_ppcct.md` DoD updated with alignment gate
- [ ] `full_codebase_refactor.md` Requirements item 8 updated with full protocol language
- [ ] Move this doc to `implemented/`

## Lessons Learned

_(fill in after implementation)_
