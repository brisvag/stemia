import click


@click.command()
@click.argument(
    "stacks", nargs=-1, type=click.Path(exists=True, dir_okay=False, resolve_path=True)
)
@click.option("-c", "--max-classes", default=5, type=int)
def cli(stacks, max_classes):
    """Do hierarchical classification of particle stacks based on densities."""
    from pathlib import Path

    import mrcfile
    import numpy as np
    import pandas as pd
    import plotly.express as px
    from matplotlib import pyplot as plt
    from rich import print
    from rich.progress import Progress
    from scipy.cluster.hierarchy import dendrogram, fcluster, linkage

    from stemia.utils.image_processing import compute_dist_field, create_mask_from_field

    if not stacks:
        return

    with mrcfile.open(stacks[0], header_only=True) as mrc:
        shape = mrc.header[["nx", "ny"]].item()

    radius = min(shape) / 2
    dist_field = compute_dist_field(
        shape=shape,
        field_type="sphere",
    )
    mask = create_mask_from_field(
        field=dist_field,
        radius=radius * 0.6,
        padding=radius * 0.8,
    )

    field_squared = dist_field**2

    images = {}

    print(f"Running with {max_classes} classes.")

    df = pd.DataFrame(columns=["total_density", "radius_of_gyration"])
    df.index.name = "image"
    with Progress() as progress:
        for st in progress.track(stacks, description="Reading data..."):
            data = mrcfile.read(st)
            images[Path(st).stem] = data
            for idx, img in enumerate(
                progress.track(data, description="Calculating features...")
            ):
                img_name = f"{Path(st).stem}_{idx}"
                img -= img.min()
                img /= img.mean()
                img *= mask
                total_density = img.sum()
                gyr = np.sqrt(np.sum(field_squared * img))
                df.loc[img_name] = [total_density, gyr]
            progress.update(progress.task_ids[-1], visible=False)

        proc_task = progress.add_task("Classifying...", total=3)

        Z = linkage(df.to_numpy(), "centroid", optimal_ordering=True)
        progress.update(proc_task, advance=1)
        classes = fcluster(Z, t=max_classes, criterion="maxclust")
        progress.update(proc_task, advance=1)
        df["class"] = classes

        fig = plt.figure(figsize=(50, 20))
        _ = dendrogram(Z)
        plt.savefig("classification.png")
        df.to_csv("classification.csv", sep="\t")
        df["name"] = df.index

        fig = px.scatter(
            df,
            x="total_density",
            y="radius_of_gyration",
            color="class",
            hover_name="name",
        )
        fig.show()
        progress.update(proc_task, advance=1)

        for cl, df_cl in progress.track(
            df.groupby("class"), description="Splitting classes..."
        ):
            stacked = {}
            for img in df_cl.index:
                *img_name, idx = img.split("_")
                img_name = "_".join(img_name)
                idx = int(idx)
                stacked.setdefault(img_name, []).append(images[img_name][idx])
            for img_name, data in stacked.items():
                mrc = mrcfile.new(
                    f"{img_name}_class_{cl:04}.mrc", np.stack(data), overwrite=True
                )
                mrc.close()
