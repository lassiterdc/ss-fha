# Contributing

## Development setup

1. Fork and clone the repository
2. Create a conda environment or virtual environment
3. Install in development mode: `pip install -e ".[docs]"`
4. Install pre-commit hooks: `pre-commit install`

## Workflow

- Create a feature branch from `main`
- Make changes with tests
- Run `ruff check .` and `ruff format .`
- Run `pytest`
- Submit a pull request

## Documentation

Build docs locally:

```bash
pip install -e ".[docs]"
mkdocs serve
```

---

## Development Principles

### Never commit without explicit permission

All commits require prior approval from the developer.

### Raise questions rather than make assumptions
When you encounter uncertainty or discrepancies — especially when implementing a pre-written plan that may have stale components — err on the side of caution and ask the developer how to proceed.

### Plan, then implement
Follow a plan-then-implement strategy. If implementing a plan uncovers a need to change it or its success criteria — including deviations from the planned approach, scope changes, or new risks — raise the discrepancy before continuing rather than adapting silently.

### `#user:` prefixed statements mark developer comments that must be addressed before plan implementation

In planning documents, all comments followed by `#user:` are meant as feedback for the AI and must ALL be addressed before any implementation can take place. The comments should be removed once they are addressed. In addressing these comments, implications for the entire planning document should be considered since they can yield major changes. The user comments can only be removed with written confirmation from the developer that the comment has been sufficiently addressed.

### Let's do things right, even if it takes more effort
- Always be on the lookout for better ways of achieving development goals and raise these ideas
- Raise concerns when you suspect the developer is making design decisions that diverge from best practices
- Look for opportunities to make code more efficient (vectorize operations, avoid loops with pandas, etc.)
- Be alert for mathematical errors in probability and return period calculations

### Backward compatibility is NOT a priority

**Rationale**: Single developer codebase. Clean code matters more than preserved APIs. Git history is the safety net.

When refactoring:
- ❌ Don't add deprecation warnings
- ❌ Don't keep old APIs "for compatibility"
- ❌ Don't create compatibility shims or aliases
- ✅ Do update all usage sites immediately
- ✅ Do delete obsolete code completely

### Most function arguments should not have defaults

Default function arguments can lead to difficult-to-debug unexpected behavior. Avoid default values unless a default is almost always the correct choice (e.g., `verbose=True`). This is especially true for configuration fields that users populate — the user should make an intentional choice about every input.

### Avoid aliases

Do not create aliases for functions, classes, or variables. An alias is a second name for the same thing — it creates confusion about which name is authoritative and is a form of backward-compatibility shim. If something needs renaming, rename it and update all call sites.

### No cruft/all variables, imports, and function arguments must be used

Unused elements are a signal that implementation may be incomplete. Treat them as an investigation trigger, not just lint to suppress.

If you come across an unused variable, import, or function argument, investigate before removing:
1. Check whether the surrounding implementation is incomplete
2. Find planning documents that touched that function and determine whether implementation is planned
3. If still uncertain, raise the concern with the developer with hypotheses about why it exists
4. The only exception: elements included for a currently-planned implementation, marked with a comment referencing the planning document

Report your observations, hypotheses, and recommendations to the developer.

After investigation and with approval from the developer, remove unused code, dead branches, commented-out blocks, and stale imports.

### Functions have docstrings, type hints, and type checking

Apply this standard to code you write or modify. For existing code in touched scripts, apply organically — accumulate adherence naturally as scripts are touched rather than doing a global retrofit pass.

### Fail-fast

Critical paths must raise exceptions; never silently return `False` or `None` on failure.

### Preserve context in exceptions

Exceptions should include file paths, return codes, and log locations for actionable debugging. Where appropriate, raise custom exceptions from `ss_fha.exceptions` with full contextual attributes.

### Prefer log-based completion checks over file existence checks

A file may exist but be corrupt, incomplete, or from a previous failed run. File existence checks can mask errors when log checks are available.

- **Exception**: File existence is appropriate for verifying *input* files before reading them.

### Use Pydantic models and user-defined YAMLs for controlling inputs

### Runner scripts take command line arguments for Snakemake compatibility

To accommodate Snakemake implementation, outputs should be generated from executing runner scripts that take command line arguments to control their operation. Robust logging in runner scripts should be directed to stdout, which will be collected by Snakemake and recorded in logfiles.

### Snakemake rule generation should use wildcards

Snakemake rule generation in `workflow.py` should use wildcards as much as possible to keep Snakefiles a reasonable human-readable length. It may be necessary to write loops that generate many different rules, but that should only be done if there isn't a cleaner, more canonical Snakemake approach.

### No shims for poorly formatted inputs

If the case study data in the hydroshare data folder is formatted in a way that is inconvenient for analysis, the AI should make a recommendation to the developer on how to best format the data. This is helpful because it could inform improvements to other prior processes (stochastic weather generation and ensemble simulation result processing).

### Data type preferences

- For point, line, and polygon geospatial data, prefer GeoJSON
- For multidimensional outputs, prefer zarr (v3) with support for NetCDF

### Keep system-agnostic software

System-specific information belongs in user-defined configuration files. Avoid hardcoded paths or machine-specific constants in core code.

### All hardcoded constants in one module

All module-level constants (named `UPPER_SNAKE_CASE`) belong in `src/ss_fha/constants.py`. Case-study-specific values (e.g. `n_years_synthesized`, `return_periods`, rain windows) are user YAML config values, not constants. Do not define constants in individual modules; import from `constants.py` instead.

### Type checking

Type checking is handled by pyright/Pylance via `pyrightconfig.json` and `.vscode/settings.json`:

- `pyrightconfig.json` controls the pyright CLI and is also read by Pylance
- `.vscode/settings.json` controls Pylance-specific overrides via `python.analysis.diagnosticSeverityOverrides`
- Do not use `ty` (removed from project; too immature for production use as of early 2026)

Resolve type errors with code changes where possible:
- Use `.to_numpy()` instead of `.values` when `ndarray` is required
- Use `str(s.name)` or `str(n) for n in index.names` to narrow `Hashable | None` → `str`
- Use `int(series.idxmin())` to narrow `int | str` when the index is guaranteed integer
- Use `cast(pd.DataFrame, ...)` to narrow `Series | DataFrame` from `.loc`

Suppress whole diagnostic categories globally rather than scattering `# type: ignore`:
- `pyrightconfig.json`: `reportIndexIssue = "none"`, `reportUnreachable = "none"`, `reportUnusedFunction = "none"`
- `.vscode/settings.json`: matching overrides

Fix "unreachable code" cascade hints with code changes:
- Explicitly annotate accumulator lists: `lst: list[pd.DataFrame] = []`
- Wrap `.loc[]` / `.apply()` calls that return `Never` with `cast(pd.DataFrame, ...)`

Use `# type: ignore[index]` for isolated pandas `.loc` / `pd.IndexSlice` calls where global suppression doesn't apply. Use `# type: ignore` without a code only as a last resort; require developer approval.

### Track project-agnostic utility candidates

When writing utility functions that could plausibly belong in a shared library (e.g., general-purpose file I/O helpers, generic array operations), note them in `docs/planning/utility_package_candidates.md`. Do not extract them immediately — track them so they can be evaluated together.

---

## Deploying

A reminder for the maintainers on how to deploy.

1. Write your release notes in `HISTORY.md` and commit:

    ```sh
    git add HISTORY.md
    git commit -m "Add release notes for vX.Y.Z"
    ```

2. Bump the version and commit:

    ```sh
    uv version patch  # or: minor, major
    git add pyproject.toml uv.lock
    git commit -m "Bump version to X.Y.Z"
    ```

3. Push, then tag and push the tag:

    ```sh
    git push
    just tag
    ```

GitHub Actions will automatically publish to PyPI when the tag is pushed. See `.github/workflows/publish.yml` for details.

---

## AI Workflow

This project uses Claude Code with structured workflow skills. When working with AI assistance:

- `CONTRIBUTING.md` — development principles and working norms (this file)
- `CLAUDE.md` — AI-specific working norms and project context (auto-loaded by Claude Code)
- `architecture.md` — project structure and key modules

Workflow skills (available globally, invoke by name):
- `/implementation-plan` — design a complete plan before coding
- `/proceed-with-implementation` — preflight check before implementing a plan
- `/qaqc-and-commit` — post-implementation QA review and commit
