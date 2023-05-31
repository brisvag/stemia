import click


@click.command()
@click.argument('inputs', nargs=-1, type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-b', '--binning', type=float, help='binning amount', required=True)
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
def cli(inputs, binning, overwrite):
    """
    Bin mrc images to the specified pixel size using fourier cropping.
    """
    from pathlib import Path
    import mrcfile
    import numpy as np
    from scipy.fft import fftn, fftshift, ifftn, ifftshift
    from rich.progress import track

    for input in track(inputs, description='Cropping...'):
        inp = Path(input)
        output = inp.with_stem(inp.stem + f'_bin{binning}')
        if Path(output).is_file() and not overwrite:
            raise click.UsageError(f'{output} exists but "-f" flag was not passed')

        with mrcfile.open(input) as mrc:
            px_size = mrc.voxel_size.x
            data = mrc.data

        ft = fftshift(fftn(data))
        center = np.array(data.shape) // 2
        shifts_from_center = (np.array(data.shape) // (binning * 2)).astype(int)
        crop_slice = tuple(slice(c - s, c + s) for c, s in zip(center, shifts_from_center))
        ft_cropped = ft[crop_slice]
        cropped = ifftn(ifftshift(ft_cropped)).real

        with mrcfile.new(output, cropped, overwrite=overwrite) as mrc:
            mrc.voxel_size = px_size * binning
