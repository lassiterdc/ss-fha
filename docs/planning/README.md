# Planning Documents

Planning documents live here, organized by type. Each type has a `completed/` subdirectory.

## Structure

```
docs/planning/
├── bugs/
│   └── completed/
├── features/
│   └── completed/
└── refactors/
    └── completed/
```

## Lifecycle

- **Active**: document lives in the type directory (`bugs/`, `features/`, `refactors/`)
- **Completed**: move to `completed/` within the same type directory
- **Deprioritized**: move to `shelved/` (create if needed)
- **No longer relevant**: delete

## Naming convention

All planning docs use `YYYY-MM-DD_descriptive_snake_case_name.md` where the date is the creation date.

## Multi-phase plans

For plans with phases committed separately, use a subdirectory:

```
docs/planning/features/2026-01-15_my_feature/
├── master.md
├── 1_phase_one.md
├── 2_phase_two.md
└── implemented/
```

See `CLAUDE.md` for the full lifecycle rules.
