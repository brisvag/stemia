import click


@click.command()
@click.argument(
    "classes", type=click.Path(exists=True, dir_okay=False, resolve_path=True)
)
@click.option(
    "-l", "--update-list", is_flag=True, help="Whether to update the list of entries."
)
@click.option(
    "-p",
    "--update-projections",
    is_flag=True,
    help="Whether to update the projection database.",
)
@click.option(
    "-r",
    "--bin-resolution",
    type=float,
    default=4,
)
@click.option(
    "-q",
    "--emdb-query",
    type=str,
    default="",
)
@click.option(
    "--emdb-save-path",
    type=click.Path(dir_okay=True, file_okay=False),
    default="~/.emdb_projections/",
    help="Where to save the database of projections.",
)
@click.option("-f", "--overwrite", is_flag=True, help="overwrite output if exists")
def cli(
    classes,
    update_list,
    update_projections,
    bin_resolution,
    emdb_query,
    emdb_save_path,
    overwrite,
):
    """Find emdb entries similar to the given 2D classes."""
    import json
    import re
    from pathlib import Path

    import mrcfile
    import numpy as np
    import sh
    from rich.progress import Progress

    from stemia.utils.image_processing import (
        coerce_ndim,
        correlate_rotations,
        match_px_size,
        normalize,
        rescale,
        rotated_projections,
    )

    emdb_save_path = Path(emdb_save_path).expanduser().resolve()

    rsync = sh.rsync.bake("-rltpvzhu", "--info=progress2")

    if update_list:
        print("Updating header database...")
        rsync(
            "rsync.ebi.ac.uk::pub/databases/emdb/structures/*/header/*v30.xml",
            emdb_save_path,
        )

    entries = sorted(emdb_save_path.glob("*.xml"))

    with Progress() as prog:
        if update_projections:
            for entry in prog.track(
                entries, description="Updating projection database..."
            ):
                entry_id = re.search(r"emd-(\d+)", entry.stem).group(1)

                proj_path = emdb_save_path / f"{entry_id}_proj.mrc"
                if proj_path.exists() and not overwrite:
                    continue

                img_path = emdb_save_path / f"emd_{entry_id}.map"

                if not img_path.exists():
                    gz_name = f"emd_{entry_id}.map.gz"
                    sync_path = f"rsync.ebi.ac.uk::pub/databases/emdb/structures/EMD-{entry_id}/map/{gz_name}"
                    rsync(sync_path, emdb_save_path)
                    sh.gzip("-d", str(emdb_save_path / gz_name))

                with mrcfile.open(img_path) as mrc:
                    img = mrc.data
                    px_size = mrc.voxel_size.x.item()

                if px_size < bin_resolution:
                    img = rescale(img, px_size, bin_resolution)
                    px_size = bin_resolution
                img = normalize(img, inplace=True)
                proj = rotated_projections(img, healpix_order=2)

                with mrcfile.new(
                    emdb_save_path / proj_path,
                    proj.astype(np.float32),
                    overwrite=overwrite,
                ) as mrc:
                    mrc.voxel_size = (px_size, px_size, 1)
                    mrc.set_image_stack()

                img_path.unlink()

        projections = sorted(emdb_save_path.glob("*_proj.mrc"))

        with mrcfile.open(classes) as mrc:
            class_data = coerce_ndim(mrc.data, 3)
            class_px_size = mrc.voxel_size.x.item()

        main_task = prog.add_task(description="Input classes...")
        task = prog.add_task(description="Entries...")
        subtask = prog.add_task(description="Cross-correlating...")

        corr_values = []
        for _cls_idx, cls in enumerate(class_data):
            corr_values_cls = {}
            corr_values.append(corr_values_cls)
            for proj_path in projections:
                entry_id = re.match(r"\d+", proj_path.stem).group()
                corr_values_cls[entry_id] = 0
                with mrcfile.open(proj_path) as mrc:
                    proj_stack_data = mrc.data
                    proj_px_size = mrc.voxel_size.x.item()

                cls_reshaped, proj_stack_reshaped, px_size = match_px_size(
                    cls, proj_stack_data, class_px_size, proj_px_size, axes=(-2, -1)
                )
                cls_reshaped = cls_reshaped.astype(np.float32)
                proj_stack_reshaped = proj_stack_reshaped.astype(np.float32)

                for cc in correlate_rotations(cls_reshaped, proj_stack_reshaped):
                    corr_values_cls[entry_id] = cc

                    prog.update(subtask, advance=100 / len(proj_stack_data))
                prog.update(subtask, completed=0)
                prog.update(task, advance=100 / len(projections))
            prog.update(task, completed=0)
            prog.update(main_task, advance=100 / len(class_data))
        prog.update(subtask, completed=100)
        prog.update(task, completed=100)
        prog.update(main_task, completed=100)

        with open("/home/lorenzo/tmp/correlation_output.json", "w+") as f:
            json.dump(corr_values, f)


if __name__ == "__main__":
    cli()
