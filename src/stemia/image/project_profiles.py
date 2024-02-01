#!/usr/bin/env python3

import click


@click.group()
def cli():
    """Project re-extracted and straightened membranes and get some stats."""
    pass


@cli.command()
@click.argument(
    "paths", nargs=-1, type=click.Path(exists=True, dir_okay=False, resolve_path=True)
)
@click.option(
    "-o", "--output", required=True, type=click.Path(dir_okay=True, resolve_path=True)
)
@click.option("-s", "--chunk-size", type=int, default=35)
@click.option("-f", "--overwrite", is_flag=True)
def prepare(paths, output, chunk_size, overwrite):
    """Generate and select 2D chunked projections for the input data."""
    import warnings
    from collections import defaultdict
    from pathlib import Path

    import mrcfile
    import napari
    import numpy as np
    from PIL import Image

    def normalize(arr):
        arr = arr - np.nanmin(arr)
        return arr / np.nanmax(arr)

    def get_correct_entry(viewer, event):
        for lay in reversed(viewer.layers):
            shift = lay._translate_grid[0]
            pos = np.array(event.position)[0]
            if np.all(pos >= shift):
                return lay.name
        return None

    def open_entry(viewer, event):
        if event.modifiers:
            return
        entry = get_correct_entry(viewer, event)
        if entry is not None:
            viewer.layers[entry].visible = not viewer.layers[entry].visible

    outdir = Path(output)
    outdir.mkdir(parents=True, exist_ok=True)

    proj_z = defaultdict(dict)
    px_sizes = {}
    for volume_path in paths:
        volume_path = Path(volume_path)
        name = volume_path.stem
        subdir = outdir / name
        subdir.mkdir(parents=True, exist_ok=True)
        with mrcfile.open(volume_path) as mrc:
            px_size = mrc.voxel_size.x.item()
            px_sizes[name] = px_size
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "mean of empty slice")
                full = normalize(np.nanmean(mrc.data, axis=0))

        chunks = np.split(full, range(chunk_size, full.shape[0], chunk_size), axis=0)
        # fuse last two chunks if the last one is too small
        if len(chunks) > 1 and chunks[-1].shape[0] < chunk_size / 2:
            chunks = chunks[:-2] + [np.concatenate(chunks[-2:], axis=0)]
        for idx, chunk in enumerate(chunks):
            proj_z[volume_path.stem][idx] = chunk

        # save full projections
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Data array contains NaN values")
            with mrcfile.new(
                subdir / f"{name}_projZ.mrc", full, overwrite=overwrite
            ) as mrc:
                mrc.voxel_size = px_size
        img = Image.fromarray((np.nan_to_num(full) * 255).astype(np.uint8))
        img.save(subdir / f"{name}_projZ.png", overwrite=overwrite)

    # open napari to view projections and save them
    for name, proj in proj_z.items():
        print(f"Opening {name}...")
        v = napari.Viewer()
        for idx, chunk in proj.items():
            v.add_image(
                chunk,
                name=f"{name}_{idx:02}",
                contrast_limits=(0, 1),
                metadata={"idx": idx},
            )

        v.mouse_double_click_callbacks.append(open_entry)

        v.grid.enabled = True
        v.grid.stride = -1
        v.grid.shape = (-1, 1)
        napari.run()

        to_save = [lay for lay in v.layers if lay.visible]

        print(f"Saving {name}...")
        subdir = outdir / name
        for lay in to_save:
            idx = lay.metadata["idx"]
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", "Data array contains NaN values")
                with mrcfile.new(
                    subdir / f"{name}_projZ_{idx:02}.mrc", lay.data, overwrite=overwrite
                ) as mrc:
                    mrc.voxel_size = px_sizes[name]
            img = Image.fromarray((np.nan_to_num(lay.data) * 255).astype(np.uint8))
            img.save(subdir / f"{name}_projZ_{idx:02}.png", overwrite=overwrite)


@cli.command()
@click.argument(
    "proj_dir", type=click.Path(exists=True, dir_okay=True, resolve_path=True)
)
@click.option("-f", "--overwrite", is_flag=True)
def compute(proj_dir, overwrite):
    """Take the outputs from prepare and compute statistics and plots."""
    import re
    import warnings
    from collections import defaultdict
    from inspect import cleandoc
    from pathlib import Path

    import mrcfile
    import numpy as np
    import pandas as pd
    import plotly.express as px
    from scipy.signal import find_peaks

    def normalize(arr):
        arr = arr - np.nanmin(arr)
        return arr / np.nanmax(arr)

    projs = defaultdict(dict)
    projs_avg = defaultdict(dict)
    px_sizes = {}

    proj_dir = Path(proj_dir)
    for subdir in proj_dir.iterdir():
        if not subdir.is_dir():
            print(f"Ignoring {subdir}: not a directory.")
            continue
        name = subdir.stem
        for proj in subdir.glob("*projZ_??.mrc"):
            idx = int(re.search(r"projZ_(\d\d)", proj.stem).group(1))
            with mrcfile.open(proj) as mrc:
                px_sizes[name] = mrc.voxel_size.x.item()
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", "mean of empty slice")
                    proj = normalize(np.nanmean(mrc.data, axis=0))
                    projs[name][idx] = proj
                    projs_avg[name][idx] = (
                        pd.DataFrame(proj)
                        .rolling(window=5, min_periods=1)
                        .mean()
                        .to_numpy()
                        .squeeze()
                    )

    # find peaks
    high_peaks = {}
    low_peaks = {}
    for name, ps in projs_avg.items():
        high_peaks_idx, high_peaks_props = zip(
            *[find_peaks(p, height=0.2) for p in ps.values()]
        )
        high_peaks[name] = [
            loc[prop["peak_heights"].argsort()]
            for loc, prop in zip(high_peaks_idx, high_peaks_props)
        ]
        low_peaks_idx, low_peaks_props = zip(
            *[find_peaks(1 - p, height=0.2) for p in ps.values()]
        )
        low_peaks[name] = [
            loc[prop["peak_heights"].argsort()]
            for loc, prop in zip(low_peaks_idx, low_peaks_props)
        ]

    # align main peaks
    for name in low_peaks:
        # len(p) // 2 is middle (so we don't shift much)
        first_2_peaks = np.array(
            [
                p[-2:] if len(p) >= 2 else (len(p) // 2, len(p) // 2)
                for p in low_peaks[name]
            ]
        )
        main_low_peaks = first_2_peaks.min(axis=1)

        shifts = main_low_peaks[0] - main_low_peaks
        for (k, v), shift in zip(projs[name].items(), shifts):
            projs[name][k] = np.roll(v, shift)
        for (k, v), shift in zip(projs_avg[name].items(), shifts):
            projs_avg[name][k] = np.roll(v, shift)

    # plot aligned plots
    for name in low_peaks:
        df = pd.DataFrame(projs[name])
        df.index = np.arange(len(df)) * px_sizes[name]
        df.sort_index(inplace=True, axis=1)
        df.to_csv(proj_dir / name / "profiles.csv")

        fig = px.line(df, title=f"Density profile of {name} by chunks")
        fig.update_layout(xaxis_title="Position (Å)", yaxis_title="Normalised density")
        fig.show()
        fig.write_image(proj_dir / name / "profiles.png", width=1400, height=700)

        # also average
        fig = px.line(df.mean(axis=1), title=f"Mean density profile of {name}")
        fig.update_layout(xaxis_title="Position (Å)", yaxis_title="Normalised density")
        fig.show()
        fig.write_image(proj_dir / name / "profile_average.png", width=1400, height=700)
        # save individual plots
        for col in df:
            fig = px.line(
                df[col], title=f"Density profile of {name}, chunk {int(col):02}"
            )
            fig.update_layout(
                xaxis_title="Position (Å)", yaxis_title="Normalised density"
            )
            fig.write_image(
                proj_dir / name / f"profile_{int(col):02}.png", width=1400, height=700
            )

    # calculate thicknesses
    for name in low_peaks:
        # low peaks (membranes)
        first_2_peaks = np.array(
            [p[-2:] if len(p) >= 2 else (0, 0) for p in low_peaks[name]]
        )
        thickness_dark = (
            np.abs(np.diff(first_2_peaks, axis=1)).squeeze() * px_sizes[name]
        )
        # high peaks (white band)
        first_2_peaks = np.array(
            [p[-2:] if len(p) >= 2 else (0, 0) for p in high_peaks[name]]
        )
        thickness_white = (
            np.abs(np.diff(first_2_peaks, axis=1)).squeeze() * px_sizes[name]
        )

        df = pd.DataFrame(
            {"thickness_dark_A": thickness_dark, "thickness_white_A": thickness_white},
            index=projs[name].keys(),
        )
        df.index.name = "chunk"
        df.sort_index(inplace=True)

        fig = px.violin(df, title=f"Thickness distribution of {name}")
        fig.update_layout(yaxis_title="Thickness (Å)")
        fig.show()
        fig.write_image(proj_dir / name / "thickness.png", width=700, height=700)

        df.to_csv(proj_dir / name / "thickness.csv")
        print(f"--- {name} ---")
        print(df)
        print(
            f"average thickness (dark):  {thickness_dark.mean():.2f}, std={thickness_dark.std():.2f}"
        )
        print(
            f"average thickness (white): {thickness_white.mean():.2f}, std={thickness_white.std():.2f}"
        )

    print(
        cleandoc(
            """
            NOTE: Some thicknesses are computed incorrectly due to inconsistent peak heights.
                  Look through the data and manually fix the ones that look obviously wrong
                  before continuing to the next step, or they will mess up the results.
            """
        )
    )


@cli.command()
@click.argument(
    "inputs", nargs=-1, type=click.Path(exists=True, dir_okay=True, resolve_path=True)
)
@click.option(
    "-o",
    "--output-name",
    type=str,
    help="Title/filename given to the aggregated outputs.",
)
def aggregate(inputs, output_name):
    """Aggregate the generated data into general stats about given subsets.

    Inputs are subdirectories of the project_dir from compute.
    """
    from pathlib import Path

    import pandas as pd
    import plotly.express as px

    dfs = []
    names = []

    for subdir in inputs:
        subdir = Path(subdir)
        if not subdir.is_dir():
            print(f"Ignoring {subdir}: not a directory.")
            continue
        names.append(subdir.stem)
        dfs.append(pd.read_csv(subdir / "thickness.csv", index_col=0))

    df = pd.concat(dfs)
    fig = px.violin(df, title=f"Aggregated thickness distribution of {output_name}.")
    fig.update_layout(yaxis_title="Thickness (Å)")
    fig.show()

    out_img = subdir.parent / f"thickness_{output_name}.png"
    fig.write_image(
        out_img,
        width=700,
        height=700,
    )
    print(df.describe())
    df.to_csv(out_img.with_suffix(".csv"))


if __name__ == "__main__":
    cli()
