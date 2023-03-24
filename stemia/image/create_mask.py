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

    if center is None:
        center = np.array(shape) / 2
    if ang:
        radius *= px_size
        padding *= px_size

    indices = np.stack(
        np.meshgrid(
            np.arange(0, shape[0]),
            np.arange(0, shape[1]),
            np.arange(0, shape[2]),
            indexing='ij'
        ),
        axis=-1
    ) + 0.5

    if mask_type == 'sphere':
        dists = np.linalg.norm(indices - center, axis=-1)
    elif mask_type == 'cylinder':
        line = np.full((shape[axis], 3), center)
        line[:, axis] = np.arange(shape[axis])
        new_shape = [1 for _ in shape] + [3]
        new_shape[axis] = -1
        line = line.reshape(new_shape)
        dists = np.linalg.norm(indices - line, axis=-1)
    elif mask_type == 'threshold':
        import edt
        with mrcfile.open(input, permissive=True) as mrc:
            data = mrc.data
        binarized = data > threshold
        dists = -edt.sdf(binarized)

    def smoothstep_normalized(arr, min_val, max_val):
        rng = max_val - min_val
        normalized = (arr - min_val) / rng
        smooth = np.where(normalized < 0, 0, np.where(normalized <= 1, 3 * normalized**2 - 2 * normalized**3, 1))
        return 1 - smooth

    mask = smoothstep_normalized(dists, radius, radius + padding)

    if inner_radius is not None:
        inner_mask = smoothstep_normalized(dists, inner_radius, inner_radius + padding)
        mask -= inner_mask

    with mrcfile.new(output, mask.astype(np.float32), overwrite=overwrite) as mrc:
        mrc.header.cella = cell
