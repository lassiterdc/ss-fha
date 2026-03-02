# Known Performance and Memory Risks

A persistent record of known performance bottlenecks, OOM risks, and similar technical debt items surfaced during implementation. Each entry documents where the risk lives, what was done, and what to try if problems arise.

This file is a reference — do not fix issues here, create separate bug/feature docs for actionable work.

---

## Risk 1: Dask quantile computation slow at full scale (Workflow 2 combine step)

**Surfaced**: 2026-03-02, work chunk 03B preflight
**File(s)**: `src/ss_fha/runners/bootstrap_combine_runner.py`, `src/ss_fha/analysis/uncertainty.py`
**Severity**: Medium — only affects full-scale Norfolk runs, not synthetic tests

**Description**: The combine runner uses `xr.open_mfdataset` + Dask to open all 500 bootstrap sample zarrs lazily and compute exact quantiles across the `sample_id` dimension. At full scale (500 samples × 526×513 grid × ~3798 return periods), computing `.quantile()` on a large Dask array may be very slow or cause scheduler memory issues.

**What was tried previously**: The old code (`c1b_fpm_confidence_intervals_bootstrapping.py`) used a two-step approach:
1. Concatenate all samples into a single combined zarr (with `bs_id` dim) using `write_bootstrapped_samples_to_single_zarr()`
2. Then compute `.quantile()` on the combined zarr

This was reported as also being slow. It's unclear whether the bottleneck was the Dask quantile operation itself or inefficient chunking.

**If Dask quantile is too slow, try**:
1. Check Dask chunk sizes — the `sample_id` dimension should be chunked as one large chunk (compute quantile over all samples at once per spatial chunk)
2. Fall back to the two-step approach: concatenate samples into a combined zarr, write to disk, then compute quantiles from the materialized combined zarr
3. Use `method="closest_observation"` in `.quantile()` — avoids interpolation and may be faster
4. Profile with `dask.distributed` dashboard to identify the bottleneck

**Tracking**: Add a profiling task to Phase 6 (case study validation) if this issue is encountered.

---

## Risk 2: Full-scale `.compute()` OOM — Workflow 1 flood hazard (existing)

**Surfaced**: 2026-03-01, work chunk 03A
**File(s)**: `src/ss_fha/analysis/flood_hazard.py:200`
**Severity**: High at full scale — may require chunked writing strategy

**Description**: `ds_flood_probs.compute()` materializes ~25 GB into RAM at full scale (3700 events × 550×550 grid) before writing to zarr. This was necessary because zarr V3 has issues serializing dask masked arrays.

**Code comment**: Already documented with a warning in `flood_hazard.py`.

**If OOM occurs**:
1. Write one variable at a time using `ds[var].compute()` in a loop
2. Use `ds.to_zarr(path, compute=False)` with a Dask `.compute()` call on the delayed object
3. Investigate zarr V3 masked array support in newer versions of zarr-python

---
