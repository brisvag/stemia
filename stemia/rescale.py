from pathlib import Path

from scipy.ndimage import zoom
import click
import mrcfile


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('input', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.argument('output', type=click.Path(dir_okay=False, resolve_path=True))
@click.argument('target_pixel_size', type=float)
@click.option('--input-pixel-size', type=float, help='force input pizel size and ignore mrc header')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
def main(input, output, target_pixel_size, input_pixel_size, overwrite):
    """
    Rescale an mrc image to the specified pixel size.

    TARGET_PIXEL_SIZE: target pixel size in Angstrom
    """
    if Path(output).is_file() and not overwrite:
        raise click.UsageError(f'{output} exists but "-f" flag was not passed')
    mrc = mrcfile.open(input)
    if mrc.voxel_size.x == target_pixel_size:
        raise click.UsageError(f'{input} already at {target_pixel_size} A/px. If the header is wrong, provide an input pixel size with --input-pixel-size')
    factor = mrc.voxel_size.x / target_pixel_size
    rescaled = zoom(mrc.data, factor)
    new = mrcfile.new(output, rescaled, overwrite=overwrite)
    new.header.cella = target_pixel_size * new.header.nx
