# %%
from pathlib import Path
import xarray as xr
import TRITON_SWMM_toolkit.utils as tsut

reindexed_ensemble = Path(
    "/mnt/d/Dropbox/_GradSchool/_norfolk/_sharing/2025-06-30_research material for Aashutosh/simulation_results/reindexed_with_flood_probs/ensemble_results_reindexed.zarr"
)

hydroshare_datadir = Path("/mnt/d/Dropbox/_GradSchool/repos/ss-fha")


# %%
from numcodecs import Blosc


def return_dic_zarr_encodings_v2(ds: xr.Dataset, clevel: int = 5) -> dict:
    compressor = Blosc(cname="zstd", clevel=clevel, shuffle=Blosc.SHUFFLE)
    encoding = {}

    for var in ds.data_vars:
        if ds[var].dtype.kind in {"i", "u", "f"}:
            encoding[var] = {"compressor": compressor}

    for coord in ds.coords:
        if ds[coord].dtype.kind == "U":
            max_len = int(ds[coord].str.len().max().item())
            encoding[coord] = {"dtype": f"<U{max_len}"}

    return encoding


# %%
da = xr.open_dataset(
    reindexed_ensemble, engine="zarr", chunks="auto", consolidated=False
)["max_wlevel_m"]

# triton only
ds = (
    da.sel(dict(ensemble_type="2D_compound"))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = hydroshare_datadir / "triton_only_ensemble.zarr"
# tsut.write_zarr(ds, fname_out, compression_level=5)
encoding = return_dic_zarr_encodings_v2(ds)
ds.to_zarr(fname_out, mode="w", encoding=encoding, consolidated=False, zarr_format=2)

# %%
# tritonswmm_rain_only
ds = (
    da.sel(dict(ensemble_type="rain_only"))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = hydroshare_datadir / "tritonswmm_ensemble_rain_only.zarr"
tsut.write_zarr(ds, fname_out, compression_level=5)

# tritonswmm_surge_only
ds = (
    da.sel(dict(ensemble_type="surge_only"))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = hydroshare_datadir / "tritonswmm_ensemble_surge_only.zarr"
tsut.write_zarr(ds, fname_out, compression_level=5)

# tritonswmm_combined
ds = (
    da.sel(dict(ensemble_type="compound"))
    .squeeze(drop=True)
    .rename(dict(event_number="event_iloc"))
).to_dataset()
fname_out = hydroshare_datadir / "tritonswmm_ensemble.zarr"
tsut.write_zarr(ds, fname_out, compression_level=5)
