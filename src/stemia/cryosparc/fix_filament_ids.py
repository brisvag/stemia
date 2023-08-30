import click


@click.command()
@click.argument('star_file', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-o', '--star-output', type=click.Path(dir_okay=False, resolve_path=True),
              help='where to put the updated version of the star file [default: <STAR_FILE>_fixed_id.star]')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
def cli(star_file, star_output, overwrite):
    """
    Replace cryosparc filament ids with small unique integers.

    Relion will fail with cryosparc IDs because of overflows.
    """
    from pathlib import Path

    import pandas as pd
    import starfile

    star_output = star_output or Path(star_file).stem + '_fixed_id.star'
    if Path(star_output).is_file() and not overwrite:
        raise click.UsageError(f'{star_output} exists but "-f" flag was not passed')

    click.secho(f'Reading {star_file}...')
    data = starfile.read(star_file, always_dict=True)

    click.secho('Replacing IDs...')
    df = data['particles']
    df['rlnHelicalTubeID'] = pd.factorize(df['rlnHelicalTubeID'])[0]

    click.secho(f'Writing {star_output}...')
    starfile.write(data, star_output, overwrite=overwrite, sep=' ')
