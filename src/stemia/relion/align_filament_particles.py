import click


@click.command()
@click.argument('star_file', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-o', '--star-output', type=click.Path(dir_okay=False, resolve_path=True),
              help='where to put the updated version of the star file [default: <STAR_FILE>_aligned.star]')
@click.option('-t', '--tolerance', type=float, default=10,
              help='angle in degrees within which neighbouring particles are considered aligned')
@click.option('-c', '--consensus-threshold', type=float, default=0.7,
              help='require an angle consensus at least higher than this to use a filament.')
@click.option('-d', '--drop-below', type=int, default=4,
              help='drop filaments if they have fewer than this number of particles')
@click.option('-r', '--rotate-bad-particles', is_flag=True, help='rotate bad particles to match the rest of the filament')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
def cli(star_file, star_output, tolerance, rotate_bad_particles, consensus_threshold, drop_below, overwrite):
    """
    Fix filament PsiPriors so they are consistent within a filament.

    Read a Relion STAR_FILE with in-plane angles and filament info and
    flip any particle that's not consistent with the rest of the filament.

    If a consensus cannot be reached, or the filament has too few particles,
    discard the whole filament.
    """
    from pathlib import Path

    import numpy as np
    from scipy.interpolate import splprep, splev
    import starfile
    from rich.progress import track

    if drop_below < 4:
        raise click.UsageError('drop_below must be at least 4')

    star_output = star_output or Path(star_file).stem + '_aligned.star'
    if Path(star_output).is_file() and not overwrite:
        raise click.UsageError(f'{star_output} exists but "-f" flag was not passed')

    click.secho(f'Reading {star_file}...')
    data = starfile.read(star_file, always_dict=True)

    df = data['particles']
    groups = df.groupby('rlnHelicalTubeID')
    for _, sub in track(groups, description='Processing filaments...', total=groups.ngroups):
        if len(sub) < drop_below:
            df.loc[sub.index] = np.nan
            continue

        angles = sub['rlnAnglePsiPrior']
        coords = sub[['rlnCoordinateX', 'rlnCoordinateY']]
        tck, u = splprep(coords.T, s=0, k=3)
        deriv = splev(u, tck, der=1)
        computed_angles = np.rad2deg(np.arctan2(*deriv)) + 90
        diff = np.mod(angles - computed_angles, 360)
        is_close = (diff < tolerance) | (diff > (360 - tolerance))
        is_flipped = (diff > (180 - tolerance)) & (diff < (180 + tolerance))

        n_close = is_close.sum()
        n_flipped = is_flipped.sum()
        if n_close + n_flipped < drop_below:
            df.loc[sub.index] = np.nan
            continue

        if n_flipped > n_close:
            is_close, is_flipped = is_flipped, is_close
            n_close, n_flipped = n_flipped, n_close
            computed_angles = np.mod(computed_angles, 360) - 180

        if n_close / n_close + n_flipped < consensus_threshold:
            df.loc[sub.index] = np.nan
            continue

        is_bad = ~is_close & ~is_flipped
        df.loc[sub.index[is_close], 'rlnAnglePsiPrior'] = angles[is_close]
        df.loc[sub.index[is_flipped], 'rlnAnglePsiPrior'] = np.mod(angles[is_flipped], 360) - 180
        if rotate_bad_particles:
            df.loc[sub.index[is_bad], 'rlnAnglePsiPrior'] = computed_angles[is_bad]
        else:
            df.loc[sub.index[is_bad], 'rlnAnglePsiPrior'] = np.nan

    df.dropna(inplace=True)

    click.secho(f'Writing {star_output}...')
    starfile.write(data, star_output, overwrite=overwrite, sep=' ')
