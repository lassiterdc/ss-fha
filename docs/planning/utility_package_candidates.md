# Utility Package Candidates

This file tracks functions and classes that are project-agnostic — useful beyond both `ss_fha` and `TRITON-SWMM_toolkit` — and are candidates for extraction into a shared, pip-installable utility package.

**Why maintain this list?**
Generic utilities extracted into a separate package can be reused across projects without copy-pasting, versioned independently, and contributed back to the community. Even a small internal package avoids the "copy from TRITON-SWMM_toolkit" anti-pattern.

**How to add a candidate:**
When you write or port a function that has no domain-specific logic (no flood, no hydrology, no SWMM), add it here with a brief note on why it is generic.

**Threshold for adding:** Would a Python developer working on a completely different scientific computing project plausibly want this? If yes, it's a candidate.

---

## Candidates

| Function / Class | Current Location | Why Generic | Notes |
|-----------------|-----------------|-------------|-------|
| `WorkflowError._indent(text, prefix)` | `src/ss_fha/exceptions.py` | Pure string utility: indents each line of a multi-line string by a prefix. No domain logic. | Currently a private static method on `WorkflowError`; could be a standalone `indent_text()` function |

---

## Patterns to Watch For

- Zarr read/write with encoding defaults — any xarray-based project needs this
- Deferred validation (`ValidationResult` + `ValidationIssue` accumulator pattern) — useful in any CLI tool with complex config
- Log-based completion checks for subprocess runners — useful in any Snakemake project
- BagIt checksum validation for HydroShare downloads — useful in any HydroShare-backed project
- Platform detection helpers (`uses_slurm()`, `on_uva_hpc()`) — useful in any HPC workflow project

---

## Potential Package Names

- `hydro-utils` — domain-scoped but broad
- `scientific-workflow-utils` — very broad
- `snakemake-scientific-utils` — Snakemake-specific utilities

No decision needed yet. The list should grow organically before a package name is chosen.
