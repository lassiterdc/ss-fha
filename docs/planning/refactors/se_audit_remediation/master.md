---
impact: High
urgency: High
loe: Medium
risk: Medium
priority: 2.47
priority-label: "Core priority"
created: 2026-03-14
description: Address findings from the 2026-03-14 SE audit — reproducibility fixes, validation gaps, convention establishment, and test infrastructure improvements.
dependencies:
  - docs/planning/refactors/2026-03-04_old_code_alignment_testing/master.md  # Phase 2 (RNG fix) must precede alignment Phase 4 (event statistics)
---

# SE Audit Remediation — Master Plan

**Source audit**: `docs/planning/audit/se_review_2026-03-14.md`

## Task Understanding

### Requirements

Address the actionable findings from the 2026-03-14 SE specialist audit, organized into four implementation phases. The audit covered all implemented source code and planning documents, and surfaced issues across reproducibility, correctness, validation, conventions, and test infrastructure.

**Out of scope for this plan**:
- Section 3 findings (upcoming work risks): these are advisory notes that will be incorporated when those work chunks are implemented — they do not require code changes now
- Section 5, item 3 (protect the core/analysis/runners layering): advisory, no code change needed
- Section 5, item 4 (finish alignment testing before 03D): already tracked in the alignment testing master plan
- Section 2, item 4 (conftest.py sys.modules refactoring): deferred to alignment testing Phase 3, which will modify the same file — doing it here would create a merge conflict

### Assumptions

- All changes target the `refactoring` branch
- The existing test suite passes before this plan starts (verify during preflight)
- `ASSIGN_DUP_VALS_MAX_RETURN` promotion is safe because it is currently `False` everywhere and the new config field will default to `False`
- Deleting `utils.py` is safe because nothing imports it except `cli.py`; `cli.py` cannot be deleted because `pyproject.toml` references it as a console script entry point — instead, the placeholder content will be replaced with a minimal stub

### Success Criteria

- All 5 quick-win findings resolved
- Unseeded RNG in event statistics fixed with seeded `np.random.Generator`
- `join="outer"` replaced with `join="exact"` in `combine_and_quantile`
- Pydantic field validators added for physically impossible inputs
- `ASSIGN_DUP_VALS_MAX_RETURN` promoted from constant to config field
- Dimension name constants established in `constants.py`
- Zarr encoding pinned with explicit dtypes
- Config hash written to output zarr attrs
- `full_config` fixture passes Pydantic validation
- Test anti-patterns fixed
- `@pytest.mark.slow` convention established
- All existing tests still pass

---

## Phase Status Table

| Phase | Title | Status | Doc |
|-------|-------|--------|-----|
| 1 | Quick wins | Pending | `1_quick_wins.md` |
| 2 | Reproducibility and correctness | Pending | `2_reproducibility_and_correctness.md` |
| 3 | Conventions and infrastructure | Pending | `3_conventions_and_infrastructure.md` |
| 4 | Test speed convention | Pending | `4_test_speed_convention.md` |

---

## Cross-Phase Dependencies

```
Phase 1 (quick wins)
  └── Phase 2 (reproducibility) — uses consolidated SSFHAConfig from Phase 1
       └── Phase 3 (conventions) — threads config field from Phase 2
            └── Phase 4 (test speed) — marks tests from all prior phases
```

Phase 1 must be committed first. Phases 2 and 3 depend on Phase 1 (SSFHAConfig consolidation). Phase 4 can technically run after any other phase but should run last so it can mark all new tests.

---

## Decisions Log

1. **`cli.py` cannot be deleted** — `pyproject.toml` declares `ss_fha = "ss_fha.cli:app"` as a console script entry point. Deleting `cli.py` would break `pip install -e .`. Instead: gut the placeholder body but keep the file with a minimal `app = typer.Typer()` and a comment pointing to the 04B plan. Delete `utils.py` since nothing depends on it.

2. **`ASSIGN_DUP_VALS_MAX_RETURN` threading scope** — the constant is imported in 3 modules (`event_statistics.py`, `geospatial.py`, `empirical_frequency_analysis.py`) and used at 6 call sites. All call sites already pass it as a keyword argument to `compute_return_periods_for_series`, except the 2 uses in `compute_univariate_event_return_periods` and `compute_all_multivariate_return_period_combinations` which read it directly. The threading adds a parameter to 4 functions and passes it from 2 callers. Manageable.

3. **conftest.py refactoring deferred** — Section 2.4 (sys.modules manipulation) is deferred to alignment testing Phase 3 to avoid conflicting edits. Noted as a cross-plan dependency.

4. **`join="exact"` is correct for current use** — all bootstrap samples in the Norfolk case study use the same event pool, so `return_pd_yrs` axes should be identical. If a future case study needs ragged axes, that will require a new design (and a config flag to opt in).

---

## Definition of Done

- [ ] All phase docs moved to `implemented/`
- [ ] All existing tests pass after each phase commit
- [ ] No new `# TODO` comments introduced (use planning docs for deferred work)
- [ ] If any performance or memory risks were surfaced, entries added to `docs/planning/bugs/tech_debt_known_risks.md`
- [ ] Before moving to `completed/`, run the pre-completion accuracy check from `prompts/instructions/protocols/plan-accuracy-gate.md`
- [ ] Update any active plan `dependencies:` entries that reference the old path so they point to the new path
- [ ] Set `completed: true` in this plan's YAML frontmatter, then move it to `completed/` and run `scripts/generate_planning_tables.py --planning-dir docs/planning`
- [ ] Move the entire master plan subdirectory to `completed/` in the final phase's commit — do not move it until all phases are done
