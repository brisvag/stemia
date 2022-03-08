import click


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True), default='.')
@click.option('-d', '--dry-run', is_flag=True, help='only print some info, without running the commands')
@click.option('-t', '--tilt-axis', type=str, help='starting tilt axis for AreTomo, if any')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite any previous existing run')
@click.option('--ccderaser', type=str, default='ccderaser', help='command for ccderaser')
@click.option('--aretomo', type=str, default='AreTomo', help='command for aretomo')
def main(warp_dir, dry_run, ccderaser, aretomo, tilt_axis, overwrite):
    """
    run aretomo on a warp directory (after imod stacks were generated).
    Requires ccderaser and AreTomo.

    Assumes the default Warp directory structure with generated imod stacks
    """
    import subprocess
    from pathlib import Path
    import re
    import shutil
    import GPUtil
    from inspect import cleandoc
    import mrcfile

    if not shutil.which(ccderaser):
        raise click.UsageError('ccderaser is not available on the system')
    gpus = [gpu.id for gpu in GPUtil.getGPUs()]
    if not gpus:
        raise click.UsageError('you need at least one GPU to run AreTomo')

    warp_dir = Path(warp_dir)
    imod_dir = warp_dir / 'imod'
    if not imod_dir.exists():
        raise click.UsageError('warp directory does not have an `imod` subdirectory')

    ts_list = sorted(list(imod_dir.iterdir()))
    if dry_run:
        newline = '\n'
        click.secho(cleandoc(f'''
            Warp directory:
                - {warp_dir}
            Tilt series found:{''.join(f'{newline}{" " * 16}- {ts.stem}' for ts in ts_list)}
        '''))
        click.get_current_context().exit()

    def check_output_exists(ts_name):
        for ts_dir in ts_list:
            file = Path(f'{ts_dir / ts_dir.stem}.mrc.xf')
            if file.exists() and not overwrite:
                raise FileExistsError(f'{file} already exists; use -f/--overwrite to overwrite any existing files')

    with click.progressbar(ts_list, label='Fixing...', item_show_func=lambda x: str(x.stem if x is not None else '')) as bar:
        for ts_dir in bar:
            ts_name = ts_dir / ts_dir.stem
            raw = f'{ts_name}.mrc.st'
            fixed = f'{ts_name}_fixed.mrc'

            # run ccderaser, defaults from etomo
            ccderaser_cmd = f'{ccderaser} -input {raw} -output {fixed} -find -peak 8.0 -diff 6.0 -big 19. -giant 12. -large 8. -grow 4. -edge 4'
            subprocess.run(ccderaser_cmd.split(), capture_output=True, check=True,)

    with click.progressbar(ts_list, label='Normalizing...', item_show_func=lambda x: str(x.stem if x is not None else '')) as bar:
        for ts_dir in bar:
            fixed = f'{ts_name}_fixed.mrc'
            normalized = f'{ts_name}_norm.mrc'

            # normalize to mean 0 and stdev 1
            with (
                mrcfile.open(fixed) as mrc,
                mrcfile.new(normalized, overwrite=overwrite) as mrc_norm
            ):
                mrc_norm.set_data((mrc.data - mrc.data.mean()) / mrc.data.std())

    warn = []
    with click.progressbar(ts_list, label='Aligning...', item_show_func=lambda x: str(x.stem if x is not None else '')) as bar:
        for ts_dir in bar:
            normalized = f'{ts_name}_norm.mrc'
            aligned = f'{ts_name}_aligned.mrc'
            tilt = f'{ts_name}.mrc.rawtlt'
            xf = f'{ts_name}.xf'
            xf_warp = f'{ts_name}.mrc.xf'  # needs to be like this for warp to see it

            # run aretomo with basic settings
            tilt_axis_opt = f'-TiltAxis {tilt_axis}' if tilt_axis is not None else ''
            aretomo_cmd = f'{aretomo} -InMrc {normalized} -OutMrc {aligned} -AngFile {tilt} -OutXF 1 {tilt_axis_opt} -TiltCor 1 -Gpu {gpus[0]} -VolZ 0'
            proc = subprocess.run(aretomo_cmd.split(), capture_output=True, check=True)

            # rename so warp sees it
            Path(xf).rename(xf_warp)

            # find any images removed by aretomo cause too dark (should not happen with normalization)
            to_skip = []
            for line in proc.stdout.decode().split('\n'):
                if match := re.search(r'Remove image at (\S+) degree', line):
                    to_skip.append(match.group(1))

            if to_skip:
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
                    click.secho(f'doing stuff with {xml}')
                    xml.write_text(replaced)

    if warn:
        click.secho(f'WARNING: somehow found the wrong number of xml files in {warp_dir}')
        click.secho(f'Check the log and manually disable tilts in Warp for: {", ".join(warn)}.')
