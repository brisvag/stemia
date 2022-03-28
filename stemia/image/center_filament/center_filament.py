import click


@click.command()
@click.argument('input', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.argument('output', type=click.Path(dir_okay=False, resolve_path=True), required=False)
@click.option('-s', '--update-star', 'starfile', type=click.Path(exists=True, dir_okay=False, resolve_path=True),
              help='a RELION .star file to update with new particle positions')
@click.option('-o', '--star-output', type=click.Path(dir_okay=False, resolve_path=True),
              help='where to put the updated version of the star file. Only used if -s is passed [default: STARFILE_centered.star]')
@click.option('--update-by', type=click.Choice(['class', 'particle']), default='class', show_default=True,
              help='whether to update particle positions by classes or 1 by 1. Only used if -s is passed')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
@click.option('-n', '--n-filaments', default=2, help='number of filaments on the image', show_default=True)
@click.option('-p', '--percentile', default=85, help='percentile for binarisation', show_default=True)
def cli(input, output, starfile, star_output, update_by, n_filaments, percentile, overwrite):
    """
    Center an mrc image (stack) containing filament(s).

    Can update particles in a RELION .star file accordingly.
    If OUTPUT is not given, default to INPUT_centered.mrc
    """
    from .funcs import center_filaments, update_starfile
    from pathlib import Path
    from ..utils.io_ import read_mrc, write_mrc, read_particle_star, write_particle_star
    from ..utils.image_processing import coerce_ndim

    # don't waste time processing if overwrite is off and output exists
    output = output or Path(input).stem + '_centered.mrc'
    if Path(output).is_file() and not overwrite:
        raise click.UsageError(f'{output} exists but "-f" flag was not passed')
    # make sure starfile is readable
    if starfile:
        df, optics = read_particle_star(starfile)
    star_output = star_output or Path(starfile).stem + '_centered.star'

    if Path(star_output).is_file() and not overwrite:
        raise click.UsageError(f'{output} exists but "-f" flag was not passed')

    imgs, header = read_mrc(input)
    imgs = coerce_ndim(imgs, ndim=3)

    out_imgs, shifts, angles = center_filaments(imgs, n_filaments=n_filaments, percentile=percentile)

    if starfile:
        df = update_starfile(df, shifts, angles, optics)

    click.secho('Writing output files...')
    write_mrc(out_imgs, output, overwrite=overwrite, from_header=header)
    write_particle_star(df, star_output, overwrite=overwrite, optics=optics)
    click.secho('Done!')
