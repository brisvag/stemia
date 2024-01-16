import click


@click.command()
@click.argument(
    "input", type=click.Path(exists=True, dir_okay=False, resolve_path=True)
)
@click.argument("output", type=click.Path(dir_okay=False, resolve_path=True))
@click.option(
    "-t",
    "--mask-type",
    type=click.Choice(["sphere", "cylinder", "threshold"]),
    default="sphere",
)
@click.option(
    "-c", "--center", type=str, help="center of the mask (comma-separated floats)"
)
@click.option(
    "-a", "--axis", type=int, default=0, help="main symmetry axis (for cylinder)"
)
@click.option(
    "-r",
    "--radius",
    type=float,
    required=True,
    help='radius of the mask. If thresholding, equivalent to "hard padding"',
)
@click.option(
    "-i", "--inner-radius", type=float, help="inner radius of the mask (if any)"
)
@click.option("-p", "--padding", type=float, default=3, help="smooth padding")
@click.option(
    "--ang/--px",
    default=True,
    help="whether the radius and padding are in angstrom or pixels",
)
@click.option(
    "--threshold", type=float, help="threshold for binarization of the input map"
)
@click.option("-f", "--overwrite", is_flag=True, help="overwrite output if exists")
def cli(
    input,
    output,
    mask_type,
    radius,
    inner_radius,
    center,
    axis,
    padding,
    ang,
    threshold,
    overwrite,
):
    """
    Create a mask for INPUT.

    Axis order is zyx!
    """
    from pathlib import Path

    import mrcfile
    import numpy as np
    from rich.progress import Progress

    from ..utils.image_processing import compute_dist_field, create_mask_from_field

    if Path(output).is_file() and not overwrite:
        raise click.UsageError(f'{output} exists but "-f" flag was not passed')

    center = None if center is None else np.array([float(c) for c in center.split(",")])

    with mrcfile.open(input, header_only=True, permissive=True) as mrc:
        cell = mrc.header.cella
        shape = mrc.header[["nx", "ny", "nz"]].item()
        px_size = mrc.voxel_size.item()[0]

    if mask_type == "threshold":
        # data is needed for thresholding mode
        with mrcfile.open(input, header_only=False, permissive=True) as mrc:
            image = mrc.data
    else:
        image = None

    if ang:
        radius *= px_size
        padding *= px_size

    with Progress() as progress:
        task = progress.add_task("Computing distance field...", total=None)
        dist_field = compute_dist_field(
            shape=shape,
            field_type=mask_type,
            image=image,
            center=center,
            axis=axis,
            threshold=threshold,
        )
        progress.update(task, total=1, completed=1)

        task = progress.add_task("Generating mask...", total=None)
        mask = create_mask_from_field(
            field=dist_field,
            radius=radius,
            padding=padding,
        )

        with mrcfile.new(output, mask.astype(np.float32), overwrite=overwrite) as mrc:
            mrc.header.cella = cell
        progress.update(task, total=1, completed=1)
