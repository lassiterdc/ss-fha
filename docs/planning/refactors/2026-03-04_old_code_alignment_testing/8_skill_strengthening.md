---
created: 2026-03-04
last_edited: 2026-03-04 — initial draft
---

# Phase 8: Skill Strengthening — `refactor-plan` + Lessons Learned Appendix

## Dependencies

**Upstream**: Phases 1–7 must all be complete. This phase runs last — only after all retroactive and prospective alignment work is done and the lessons learned appendix is populated.
**Downstream**: None — this is the final phase.

## Task Understanding

Two goals:
1. Populate the lessons learned appendix in `full_codebase_refactor.md` by synthesizing insights from the "Lessons Learned" sections of each phase doc in this plan
2. Strengthen the `refactor-plan` skill so future refactors automatically include the old-code alignment protocol

## Files to Modify

### `docs/planning/refactors/2026-02-25_full_codebase_refactor/full_codebase_refactor.md`

Add an `## Appendix: Old-Code Alignment Lessons Learned` section synthesizing:
- What approaches worked (direct import with `__inputs` mock, notebook fallback)
- What obstacles were encountered (sys.exit in old functions, I/O side effects)
- Which functions were hardest to align and why
- Recommendations for future refactors

### `~/dev/claude-workspace/skills/refactor-plan/SKILL.md`

Strengthen with:
- Explicit instruction to document the old-code importability strategy early in the plan
- DoD checkbox template: `- [ ] Old-code alignment test for all ported computation functions (direct import in tests/test_old_code_alignment/ or committed notebook in _old_code_to_refactor/demonstrating_functional_alignment/)`
- Reference to the `__inputs` mock pattern as a known solution for projects with script-level global imports
- Note that main-section behaviors (outside named functions) require notebook fallback by definition

Consider whether the volume of insights from the lessons learned appendix warrants creating a dedicated protocol document (e.g., `~/dev/claude-workspace/skills/refactor-plan/protocols/old_code_alignment.md`). If more than 5–6 distinct protocol points are captured, create the subdirectory and document.

## Validation Plan

Manual review of skill file and appendix quality. Cross-check that the DoD checkbox wording in the skill exactly matches what was used in Phases 2–7.

## QAQC Notes

The QAQC report for this phase must include a **Lessons Learned** section synthesizing insights from all prior phase Lessons Learned sections. This is the final synthesis — the output feeds directly into the `full_codebase_refactor.md` appendix and `refactor-plan` skill update.

## Definition of Done

- [ ] `full_codebase_refactor.md` Appendix: Old-Code Alignment Lessons Learned section written (synthesized from phase docs)
- [ ] `refactor-plan` SKILL.md updated with alignment protocol language and DoD checkbox template
- [ ] If volume warrants it: `~/dev/claude-workspace/skills/refactor-plan/protocols/` subdirectory created with protocol document
- [ ] Move this doc to `implemented/`
- [ ] Move entire `2026-03-04_old_code_alignment_testing/` plan to `completed/`

## Lessons Learned

_(fill in after implementation)_
