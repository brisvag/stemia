from pathlib import Path

import starfile
import mrcfile
import eulerangles
import click


def flip_positions(z_values, z_shape):
    return z_shape - z_values


def flip_eulers(angles):
    mat = eulerangles.euler2matrix(angles, axes='zyz', intrinsic=True, right_handed_rotation=True)
    mat[:, :, -1] *= -1
    flipped = eulerangles.matrix2euler(mat, axes='zyz', intrinsic=True, right_handed_rotation=True)
    return flipped


@click.command()
@click.argument('star_path', type=click.Path(exists=True, dir_okay=False))
@click.option('-o', '--output', type=click.Path(dir_okay=False, writable=True))
@click.option('-m', '--mrc_path', type=click.Path(exists=True, dir_okay=False))
@click.option('--star_pixel_size', type=float)
@click.option('--mrc_pixel_size', type=float)
@click.option('--z_shape', type=int)
def main(star_path, *, output=None, mrc_path=None, star_pixel_size=None, mrc_pixel_size=None, z_shape=None):
    """
    STAR_PATH: star file to flip along z
    assume all micrographs have the same shape
    """
    if mrc_path is None:
        if mrc_pixel_size is None or z_shape is None:
            raise click.UsageError('must provide either mrc_path or both mrc_pixel_size and z_shape')
    if output is None:
        sp = Path(star_path)
        output = sp.parent / (sp.stem + '_z_flipped.star')
    star = starfile.open(star_path, always_dict=True)
    euler_headers = [f'rlnAngle{angle}' for angle in ('Rot', 'Tilt', 'Psi')]
    z_header = 'rlnCoordinateZ'
    pixel_size_headers = ['rlnImagePixelSize', 'rlnDetectorPixelSize']

    for block_name, df in star.items():
        if euler_headers[0] in df.columns:
            # keep these
            break

    if star_pixel_size is None:
        for h in pixel_size_headers:
            if h in df.columns:
                star_pixel_size = df[h]
                break
        else:
            raise ValueError('could not find pixel size in star file')
    if mrc_path is not None:
        with mrcfile.open(mrc_path, header_only=True) as mrc:
            z_shape = z_shape or mrc.header.nz.item()
            mrc_pixel_size = mrc_pixel_size or mrc.voxel_size.item()[0]
    normalized_z_shape = z_shape * (mrc_pixel_size / star_pixel_size)

    df[z_header] = flip_positions(df[z_header], normalized_z_shape)
    df[euler_headers] = flip_eulers(df[euler_headers])
    starfile.write(star, output)
