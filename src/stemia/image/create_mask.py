import click


@click.command()
@click.argument('input', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.argument('output', type=click.Path(dir_okay=False, resolve_path=True))
@click.option('-t', '--mask-type', type=click.Choice(['sphere', 'cylinder', 'threshold']), default='sphere')
@click.option('-c', '--center', type=float, help='center of the mask')
@click.option('-a', '--axis', type=int, default=0, help='main symmetry axis (for cylinder)')
@click.option('-r', '--radius', type=float, required=True, help='radius of the mask. If thresholding, equivalent to "hard padding"')
@click.option('-i', '--inner-radius', type=float, help='inner radius of the mask (if any)')
@click.option('-p', '--padding', type=float, default=3, help='smooth padding')
@click.option('--ang/--px', default=True, help='whether the radius and padding are in angstrom or pixels')
@click.option('--threshold', type=float, help='threshold for binarization of the input map')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
def cli(input, output, mask_type, radius, inner_radius, center, axis, padding, ang, threshold, overwrite):
    """
    Create a mask for INPUT.

    Axis order is zyx!
    """
    from pathlib import Path
    import numpy as np
    import mrcfile

    if Path(output).is_file() and not overwrite:
        raise click.UsageError(f'{output} exists but "-f" flag was not passed')

    with mrcfile.open(input, header_only=True, permissive=True) as mrc:
        cell = mrc.header.cella
        shape = mrc.header[['nx', 'ny', 'nz']].item()
        px_size = mrc.voxel_size.item()[0]

    if ang:
        radius *= px_size
        padding *= px_size

    with mrcfile.new(output, mask.astype(np.float32), overwrite=overwrite) as mrc:
        mrc.header.cella = cell
