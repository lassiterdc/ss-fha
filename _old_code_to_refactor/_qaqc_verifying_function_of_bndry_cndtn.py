#%%
from __inputs import *
import pandas as pd
import numpy as np
import xarray as xr
import rioxarray as rxr
import geopandas as gpd
import matplotlib.pyplot as plt

dir_model = "D:/Dropbox/_GradSchool/_norfolk/stormy/flood_attribution/model_scenarios/dsgn/yr100/surge_1/"

dir_inputs = f"{dir_model}inputs/"

f_dem = f"{dir_inputs}norfolk_4.dem"
shapefile_path = f_wshed_shp
dir_triton_results = f"{dir_model}triton_compound/"
f_triton_flood_depths = f"{dir_triton_results}triton_compound_yr100_surge_1.TRITON.zarr"

dir_tritonswmm_results = f"{dir_model}tritonswmm_compound/"
f_tritonswmm_flood_depths = f"{dir_tritonswmm_results}tritonswmm_compound_yr100_surge_1.TRITON.zarr"
#%% loading DEM
# ds_dem = xr.open_dataset(f_dem)

ds_dem = rxr.open_rasterio(f_dem).sel(band = 1)


#%%
ds_design_event_tseries = xr.open_dataset(f_design_storm_tseries)

ds_triton = xr.open_dataset(f_triton_flood_depths, engine="zarr").chunk('auto')
ds_tritonswmm = xr.open_dataset(f_tritonswmm_flood_depths, engine="zarr").chunk('auto')

#%% plotting the design event
ds_design_event_tseries.sel(event_type = "surge", year = 100, event_id = 1)["waterlevel_m"].to_series().dropna().plot()


#%% triton plotting peak flood depths
mask = ds_triton.wlevel_m.max("timestep_min") > 0

da_triton_water_elevations = ds_triton.wlevel_m.max("timestep_min") + ds_dem

fig, ax = plt.subplots(dpi = 300, figsize = (5, 4))
ax.set_facecolor('lightgray')
gdf = gpd.read_file(shapefile_path)
gdf.boundary.plot(ax=ax, color='black', linewidth=1, zorder = 50)

da_triton_water_elevations.where(mask).plot(x="x", y="y", ax = ax)

#%% tritonswmm plotting peak flood depths
mask = ds_tritonswmm.wlevel_m.max("timestep_min") > 0

da_tritonswmm_water_elevations = ds_tritonswmm.wlevel_m.max("timestep_min") + ds_dem

fig, ax = plt.subplots(dpi = 300, figsize = (5, 4))
ax.set_facecolor('lightgray')
gdf = gpd.read_file(shapefile_path)
gdf.boundary.plot(ax=ax, color='black', linewidth=1, zorder = 50)

da_tritonswmm_water_elevations.where(mask).plot(x="x", y="y", ax = ax)