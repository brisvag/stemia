import click


@click.command()
@click.argument('star_file', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.argument('tilt_angle', type=float)
@click.argument('tilt_axis', type=float)
@click.option('-r', '--radians', is_flag=True, help='Provide angles in radians instead of degrees')
@click.option('-o', '--star-output', type=click.Path(dir_okay=False, resolve_path=True),
              help='where to put the updated version of the star file [default: <STAR_FILE>_tilted.star]')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
def cli(star_file, tilt_angle, tilt_axis, radians, star_output, overwrite):
    """
    Generate angle priors for a tilted dataset.

    Read a Relion STAR_FILE with in-plane angles and generate priors
    for rot and tilt angles based on a TILT_ANGLE around a TILT_AXIS.
    """
    from pathlib import Path

    import numpy as np
    import starfile
    from scipy.spatial.transform import Rotation

    star_output = star_output or Path(star_file).stem + '_tilted.star'
    if Path(star_output).is_file() and not overwrite:
        raise click.UsageError(f'{star_output} exists but "-f" flag was not passed')

    click.secho(f'Reading {star_file}...')
    data = starfile.read(star_file, always_dict=True)

    psi = np.deg2rad(data['particles']['rlnAnglePsi'])
    tilt = np.repeat(np.pi / 2, len(psi))
    rot = np.zeros(len(psi))

    rotation = Rotation.from_euler('ZYZ', np.stack([rot, tilt, psi], axis=1))

    if not radians:
        tilt_axis = np.deg2rad(tilt_axis)
        tilt_angle = np.deg2rad(tilt_angle)

    tilt_axis += np.pi / 2

    rotvec = np.array([np.cos(tilt_axis), np.sin(tilt_axis), 0]) * tilt_angle

    rot_around_axis = Rotation.from_rotvec(rotvec)
    eulers = (rotation * rot_around_axis).as_euler('ZYZ', degrees=True)

    data['particles'][['rlnAngleRot', 'rlnAngleTilt', 'rlnAnglePsi']] = eulers

    click.secho(f'Writing {star_output}...')
    starfile.write(data, star_output, overwrite=overwrite, sep=' ')
