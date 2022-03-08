import click
import subprocess
from pathlib import Path
import re
import shutil
import GPUtil
from inspect import cleandoc
import mrcfile


def check_outputs_exist(dirs, ext):
    if not isinstance(ext, tuple):
        ext = (ext,)
    for dir in dirs:
        for ex in ext:
            file = dir / f'{dir.stem}{ext}'
            if file.exists():
                raise FileExistsError(f'{file} already exists; use -f/--overwrite to overwrite any existing files')


def get_stem(path):
    if path is not None:
        return path.stem
    return ''


def run_fix(ts_list, overwrite, in_ext, ccderaser):
    if not shutil.which(ccderaser):
        raise click.UsageError('ccderaser is not available on the system')
    if not overwrite:
        check_outputs_exist(ts_list, '_fixed.mrc')
    with click.progressbar(ts_list, label='Fixing...     ', item_show_func=get_stem) as bar:
        for ts_dir in bar:
            ts_name = ts_dir / ts_dir.stem
            input = f'{ts_name}{in_ext}'
            output = f'{ts_name}_fixed.mrc'

            # run ccderaser, defaults from etomo
            ccderaser_cmd = f'{ccderaser} -input {input} -output {output} -find -peak 8.0 -diff 6.0 -big 19. -giant 12. -large 8. -grow 4. -edge 4'
            subprocess.run(ccderaser_cmd.split(), capture_output=True, check=True)


def run_normalize(ts_list, overwrite, in_ext):
    if not overwrite:
        check_outputs_exist(ts_list, '_norm.mrc')
    with click.progressbar(ts_list, label='Normalizing...', item_show_func=get_stem) as bar:
        for ts_dir in bar:
            ts_name = ts_dir / ts_dir.stem
            input = f'{ts_name}{in_ext}'
            output = f'{ts_name}_norm.mrc'

            # normalize to mean 0 and stdev 1
            with (
                mrcfile.open(input) as mrc,
                mrcfile.new(output, overwrite=overwrite) as mrc_norm
            ):
                mrc_norm.set_data((mrc.data - mrc.data.mean()) / mrc.data.std())


def run_align(ts_list, overwrite, in_ext, aretomo, tilt_axis):
    gpus = [gpu.id for gpu in GPUtil.getGPUs()]
    if not gpus:
        raise click.UsageError('you need at least one GPU to run AreTomo')
    if not overwrite:
        check_outputs_exist(ts_list, ('_aligned.mrc', 'mrc.xf'))
    warn = []
    with click.progressbar(ts_list, label='Aligning...   ', item_show_func=get_stem) as bar:
        for ts_dir in bar:
            ts_name = ts_dir / ts_dir.stem
            input = f'{ts_name}{in_ext}'
            aligned = f'{ts_name}_aligned.mrc'
            tilt = f'{ts_name}.mrc.rawtlt'
            xf = f'{ts_name}.xf'
            xf_warp = f'{ts_name}.mrc.xf'  # needs to be like this for warp to see it

            # run aretomo with basic settings
            tilt_axis_opt = f'-TiltAxis {tilt_axis}' if tilt_axis is not None else ''
            aretomo_cmd = f'{aretomo} -InMrc {input} -OutMrc {aligned} -AngFile {tilt} -OutXF 1 {tilt_axis_opt} -TiltCor 1 -Gpu {gpus[0]} -VolZ 0'
            proc = subprocess.run(aretomo_cmd.split(), capture_output=True, check=True)

            # rename so warp sees it
            Path(xf).rename(xf_warp)

            # find any images removed by aretomo cause too dark (should not happen with normalization)
            to_skip = []
            for line in proc.stdout.decode().split('\n'):
                if match := re.search(r'Remove image at (\S+) degree', line):
                    to_skip.append(match.group(1))

            if to_skip:
                warp_dir = ts_list[0].parent.parent
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


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True), default='.')
@click.option('-d', '--dry-run', is_flag=True, help='only print some info, without running the commands')
@click.option('-t', '--tilt-axis', type=float, help='starting tilt axis for AreTomo, if any')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite any previous existing run')
@click.option('--fix/--nofix', default=True, help='run ccderaser to fix the stack')
@click.option('--norm/--nonorm', default=True, help='use mrcfile to normalize the images')
@click.option('--align/--noalign', default=True, help='run aretomo to produce an alignment')
@click.option('--startfrom', type=click.Choice(('raw', 'fix', 'norm')), default='fix',
              help='use outputs from a previous run starting from this step')
@click.option('--ccderaser', type=str, default='ccderaser', help='command for ccderaser')
@click.option('--aretomo', type=str, default='AreTomo', help='command for aretomo')
def main(warp_dir, dry_run, ccderaser, aretomo, tilt_axis, overwrite, fix, norm, align, startfrom):
    """
    run aretomo on a warp directory (after imod stacks were generated).
    Requires ccderaser and AreTomo.

    Assumes the default Warp directory structure with generated imod stacks
    """
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

    if startfrom == 'raw':
        input_ext = '.mrc.st'
    elif startfrom == 'fix':
        input_ext = '_fixed.mrc'
        fix = False
    elif startfrom == 'norm':
        input_ext == '_norm.mrc'
        fix = False
        norm = False

    if fix:
        run_fix(ts_list, overwrite, input_ext, ccderaser)
        input_ext = '_fixed.mrc'

    if norm:
        run_normalize(ts_list, overwrite, input_ext)
        input_ext = '_norm.mrc'

    if align:
        run_align(ts_list, overwrite, input_ext, aretomo, tilt_axis, warp_dir)
