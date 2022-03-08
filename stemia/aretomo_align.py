import click


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True), default='.')
@click.option('--ccderaser', type=str, default='ccderaser', help='command for ccderaser')
@click.option('--aretomo', type=str, default='AreTomo', help='command for aretomo')
@click.option('--tilt_axis', type=str, help='starting tilt axis for AreTomo, if any')
def main(warp_dir, ccderaser, aretomo, tilt_axis):
    """
    run aretomo on a warp directory (after imod stacks were generated).
    Requires ccderaser and AreTomo.
    """
    import subprocess
    from pathlib import Path
    import re
    import shutil
    import GPUtil

    if not shutil.which(ccderaser):
        raise click.UsageError('ccderaser is not available on the system')
    gpus = [gpu.id for gpu in GPUtil.getGPUs()]
    if not gpus:
        raise click.UsageError('you need at least one GPU to run AreTomo')

    warp_dir = Path(warp_dir)
    imod_dir = warp_dir / 'imod'

    warn = []
    with click.progressbar(list(imod_dir.iterdir()), label='Aligning...', item_show_func=lambda x: x.stem) as bar:
        for ts_dir in bar:
            ts_name = ts_dir / ts_dir.stem
            # run ccderaser, defaults from etomo
            ccderaser_cmd = f'{ccderaser} -input {ts_name}.mrc.st -output {ts_name}.mrc_fixed.st -find -peak 8.0 -diff 6.0 -big 19. -giant 12. -large 8. -grow 4. -edge 4'
            subprocess.run(ccderaser_cmd.split(), check=True)

            # run aretomo with
            tilt_axis_opt = f'-TiltAxis {tilt_axis}' if tilt_axis is not None else ''
            aretomo_cmd = f'{aretomo} -InMrc {ts_name}.mrc_fixed.st -OutMrc {ts_name}_aretomo.mrc -AngFile {ts_name}.mrc.rawtlt -OutXF 1 {tilt_axis_opt} -TiltCor 1 -Gpu {gpus[0]} -VolZ 0'
            proc = subprocess.run(aretomo_cmd.split(), capture_output=True, check=True)

            # find removed images
            to_skip = []
            for line in proc.stdout.split('\n'):
                if match := re.search(r'Remove image at (\S+) degree'):
                    to_skip.append(match.group(1))

            log = ts_dir / 'aretomo_align.log'
            skipped = "\n".join([angle for angle in to_skip])
            log.write_text(f'Some images were too dark and were skipped by AreTomo:\n{skipped}')

            # flag as disabled in warp
            for angle in to_skip:
                glob = f'{ts_name}_*_{angle}.xml'
                xml = list(warp_dir.glob(glob))
                if len(xml) != 1:
                    warn.append(ts_name)
                    continue
                xml = xml[0]
                content = xml.read_text()
                replaced = content.replace('UnselectManual="null"', 'UnselectManual="True"')
                xml.write_text(replaced)

    if warn:
        click.secho(f'WARNING: somehow found the wrong number of xml files in {warp_dir}')
        click.secho(f'Check the log and manually disable tilts in Warp for: {", ".join(warn)}.')
