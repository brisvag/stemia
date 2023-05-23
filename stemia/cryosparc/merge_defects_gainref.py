import click


@click.command()
@click.argument('defects', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.argument('gainref', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-d', '--output-defects', type=click.Path(dir_okay=False, resolve_path=True), default='./defects.mrc')
@click.option('-o', '--output-gainref', type=click.Path(dir_okay=False, resolve_path=True), default='./gainref.mrc')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
def cli(defects, gainref, output_defects, output_gainref, overwrite):
    """
    Merge serialEM defects and gainref for cryosparc usage.

    requires active sbrgrid.
    """
    from pathlib import Path

    import sh
    import mrcfile
    import numpy as np

    if Path(output_defects).is_file() and not overwrite:
        raise click.UsageError(f'{output_defects} exists but "-f" flag was not passed')
    if Path(output_gainref).is_file() and not overwrite:
        raise click.UsageError(f'{output_gainref} exists but "-f" flag was not passed')

    click.secho('Converting gainref to mrc...')
    sh.clip('unpack', gainref, output_gainref)
    click.secho('Extracting defects file...')
    sh.clip('defects', '-D', defects, gainref, output_defects)

    click.secho('Merging...')
    d = mrcfile.read(output_defects)
    with mrcfile.open(output_gainref, 'r', permissive=True) as mrc:
        g = mrc.data
        voxel_size = mrc.voxel_size

    merged = np.where(d, 0, g)
    with mrcfile.new(output_gainref, merged, overwrite=overwrite) as mrc:
        mrc.voxel_size = voxel_size
