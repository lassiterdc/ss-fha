#  import libraries
import pandas as pd
import os
import sys
from pathlib import Path


cwd = Path.cwd()

while cwd.name != "stormy":
    cwd = cwd.parent
cwd = cwd / "flood_attribution"
# cwd = cwd / "local"
sys.path.insert(0, str(cwd))
from local.__inputs import (
    F_EXPERIMENT_DESIGN,
    DIR_FFA_SCRIPTS_LOCAL_OUTPUTS,
    PLOT_PARAMS,
)

import numpy as np
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from sklearn.preprocessing import MinMaxScaler

#  load and format data for plotting
df_experiments = pd.read_excel(
    F_EXPERIMENT_DESIGN, sheet_name=0, index_col=[1]
).sort_index(ascending=False)

df_experiments_numeric = pd.DataFrame(
    index=df_experiments.index, columns=df_experiments.columns
)

df_feature_mapping = pd.read_excel(
    F_EXPERIMENT_DESIGN, sheet_name=1, index_col=[0, 1]
).drop(columns=["varname sorting"])
# df_feature_mapping = df_feature_mapping.sort_index()
# create list of dictionaries for each variable
lst_classes = []
lst_varnames = []
# for varname, df_var_map in df_feature_mapping.groupby("variable_name"):
for varname in df_feature_mapping.reset_index()["variable_name"].unique():

    df_var_map = df_feature_mapping.loc[pd.IndexSlice[varname, :]]
    df_desc_num_map = (
        df_var_map.reset_index()
        .set_index("descriptive_index")["numeric_index"]
        .to_frame()
    )
    numeric_exp_class = (
        df_experiments[varname]
        .to_frame()
        .set_index(varname)
        .join(df_desc_num_map)
        .squeeze()
        .values
    )
    dic_numeric_class = dict(
        label=varname,
        values=numeric_exp_class,
        tickvals=np.arange(1, len(df_var_map) + 1),
        ticktext=list(df_var_map.squeeze().values),
    )
    lst_classes.append(dic_numeric_class)
    df_experiments_numeric.loc[:, varname] = numeric_exp_class
    lst_varnames.append(varname)

df = df_experiments_numeric.copy()
# df['desc'] = df_experiments['desc']
df = df.dropna(axis=1)
df = df.reset_index()
# colors = ['#e41a1c','#377eb8','#4daf4a','#984ea3','#ff7f00'] # categorical bold colors
# colors = ['#bdbdbd','#969696','#737373','#525252','#252525'] # grayscale
# colors = ["#018571", "#80cdc1", "#f5f5f5", "#dfc27d", "#a6611a"]
colors = ["#8c510a", "#d8b365", "#f6e8c3", "#c7eae5", "#5ab4ac", "#01665e"]
colors.reverse()
labels = df["desc_ascending_complexity_ranking"]

df = df.loc[:, lst_varnames]


def plot_experimental_design(
    df, n_lines=None, parallel_line_spacing=0.02, add_vert_lines=False
):
    # Normalize the data for each feature

    scale_upperlim = 0.8
    scale_lowerlim = 0.1
    scaler = MinMaxScaler(feature_range=(scale_lowerlim, scale_upperlim))
    scaler.fit(df)

    norm_df = pd.DataFrame(
        data=scaler.transform(df), index=df.index, columns=df.columns
    )

    # Create a list of the feature labels
    features = lst_varnames

    # Create the figure and axis for plotting
    fig, ax = plt.subplots(figsize=(6.5, 4), dpi=300)

    # Create the line segments for parallel coordinates
    lines = []

    # Loop over each sample (row in the data)
    y_inc = parallel_line_spacing
    y_adj = np.arange(0, len(df) * y_inc, y_inc)
    y_adj = (y_adj - y_adj.max() / 2) * -1
    for i in range(df.shape[0]):
        if n_lines is not None:
            if len(lines) >= n_lines:
                break
        sample = norm_df.loc[i, :]
        line = np.column_stack([range(len(features)), sample.values + y_adj[i]])
        lines.append(line)

        # y_adj += y_inc

    # Convert the lines to a LineCollection
    lc = LineCollection(lines, colors=colors, linewidths=3, alpha=1, zorder=2)
    lc_border = LineCollection(lines, colors="k", linewidths=3.05, alpha=1, zorder=1)

    # Add the LineCollection to the axis
    ax.add_collection(lc)
    ax.add_collection(lc_border)

    # Add vertical black lines for each feature
    if add_vert_lines:
        for i in range(len(features)):
            ax.axvline(
                x=i,
                ymin=scale_lowerlim,
                ymax=scale_upperlim,
                color="black",
                linewidth=1,
            )

    # Set the axis limits and labels
    ax.set_xlim(-0.2, len(features) - 0.2)
    ax.set_ylim(0, 1)
    ax.set_xticks(range(len(features)))
    ax.set_xticklabels(
        [feature.replace("\\n", "\n") for feature in features],
        rotation=0,
        ha="center",
        fontsize=PLOT_PARAMS["font.size"],
    )

    ax.tick_params(
        axis="x",
        which="both",  # Apply to major and minor ticks
        bottom=False,  # Hide ticks/labels from the bottom
        top=True,  # Show ticks/labels on the top
        labelbottom=False,  # Hide labels from the bottom
        labeltop=True,  # Show labels on the top
        pad=-25,
    )
    ax.set_xlabel("")

    for i, feature in enumerate(features):
        # normlized values
        s_nrmlzd = norm_df.loc[:, feature]

        # return the discrete values for this feature
        feature_mapping = df_feature_mapping.loc[pd.IndexSlice[feature, :]]

        tick_lab_adj = 0  # -0.11
        tick_positions = s_nrmlzd.sort_values().unique() + tick_lab_adj

        min_val = df.loc[:, feature].min()
        max_val = df.loc[:, feature].max()
        # tick_values = min_val + tick_positions * (max_val - min_val)
        tick_labels = feature_mapping.squeeze().astype(str).to_list()
        tick_labels = [tick_label.replace("\\n", "\n") for tick_label in tick_labels]

        # Display ticks on the axes at these positions
        ax.set_yticks(tick_positions)
        ax.set_yticklabels(tick_labels)

        # Draw the ticks along the axis
        for pos, val in zip(tick_positions, tick_labels):
            text_zorder = 99999
            ax.text(
                i,
                pos,
                val,
                color="black",
                ha="center",
                va="center",
                fontsize=PLOT_PARAMS["font.size"],
                # bbox=dict(
                #     boxstyle="round,pad=0.3",
                #     facecolor="white",
                #     edgecolor="black",
                #     alpha=1 #0.8,
                # ),
                zorder=text_zorder,
            )
            from matplotlib.patches import FancyBboxPatch

            # ax.plot(
            #     i, pos - tick_lab_adj, "o", color="black", markersize=30, zorder=3
            # )  # Black circle

            width = 0.62
            height = 0.11

            rect = FancyBboxPatch(
                (i - width / 2, pos - tick_lab_adj - height / 2),
                width,
                height,
                boxstyle="round,pad=0.02,rounding_size=0.08",
                linewidth=2,
                edgecolor="black",
                facecolor="white",
                zorder=text_zorder - 1,
            )

            ax.add_patch(rect)
    xmin, xmax = ax.get_xlim()
    ax.set_xlim(xmin - width / 2, xmax)
    # Remove the y-axis label, ticks, and tick labels
    ax.set_ylabel("")
    ax.set_yticks([])
    ax.set_yticklabels([])
    ax.tick_params(axis="x", which="both", bottom=False, top=False)
    # Remove the left, top, right, and bottom spines (axis lines)
    ax.spines["left"].set_visible(False)  # Remove the left axis line
    ax.spines["top"].set_visible(False)  # Remove top axis line
    ax.spines["right"].set_visible(False)  # Remove right axis line
    ax.spines["bottom"].set_visible(False)  # Remove bottom axis line

    # Add legend showing the relationship between color and species
    legend_elements = []
    for i, desc in enumerate(df_experiments["desc"]):
        if n_lines is not None:
            if len(legend_elements) >= n_lines:
                break
        legend_elements.append(
            Line2D([0], [0], color=colors[i], lw=4, label=desc.replace("\\n", "\n"))
        )

    if n_lines != 0:
        ax.legend(
            handles=legend_elements,
            loc="upper right",
            bbox_to_anchor=(1.02, 0.71),
            title="Experiment",
        )

    # Add an upward-pointing arrow with rotated text parallel to the arrow

    arrow_xloc = 0.02
    ax.annotate(
        "",
        xy=(arrow_xloc, 0.9),
        xycoords="axes fraction",
        xytext=(arrow_xloc, 0.05),
        textcoords="axes fraction",
        arrowprops=dict(
            facecolor="black", shrink=0.05, width=1.5, headwidth=10, headlength=10
        ),
        fontsize=PLOT_PARAMS["font.size"],
        ha="center",
        va="center",
        color="black",
        rotation=0,
        zorder=1,
    )

    ax.text(
        -0.58,
        0.5,
        "computational intensity and/or\nuncertainty accounting",
        ha="center",
        va="center",
        fontsize=PLOT_PARAMS["font.size"],
        color="black",
        rotation=90,
    )


    if n_lines is not None:
        plt.savefig(
            f"{DIR_FFA_SCRIPTS_LOCAL_OUTPUTS}experimental_design_{n_lines}.pdf",
            format="pdf",
            pad_inches=0.05,
            transparent = True
            # bbox_inches="tight",
        )
        plt.savefig(
            f"{DIR_FFA_SCRIPTS_LOCAL_OUTPUTS}experimental_design_{n_lines}.svg",
            pad_inches=0.05,
            transparent = True
            # bbox_inches="tight",
        )
        plt.clf()
    else:
        plt.savefig(
            f"{DIR_FFA_SCRIPTS_LOCAL_OUTPUTS}experimental_design.pdf",
            format="pdf",
            pad_inches=0.05,
            transparent = True
            # bbox_inches="tight",
        )
        plt.savefig(
            f"{DIR_FFA_SCRIPTS_LOCAL_OUTPUTS}experimental_design.svg",
            pad_inches=0.05,
            transparent = True
            # bbox_inches="tight",
        )

lst_plots = list(np.arange(0, len(df) + 1))
lst_plots.append(None)

for n_lines in lst_plots:
    plot_experimental_design(df, n_lines=n_lines)
