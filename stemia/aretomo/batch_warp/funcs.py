import click
import subprocess
import re
import shutil
import GPUtil
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
    skipped = False
    with click.progressbar(ts_list, label='Aligning...   ', item_show_func=get_stem) as bar:
        for ts_dir in bar:
            ts_name = ts_dir / ts_dir.stem
            input = f'{ts_name}{in_ext}'
            aligned = f'{ts_name}_aligned.mrc'
            rawtilt = f'{ts_name}.mrc.rawtlt'

            # run aretomo with basic settings
            tilt_axis_opt = f'-TiltAxis {tilt_axis}' if tilt_axis is not None else ''
            aretomo_cmd = f'{aretomo} -InMrc {input} -OutMrc {aligned} -AngFile {rawtilt} -OutXF 1 {tilt_axis_opt} -TiltCor 1 -Gpu {gpus[0]} -VolZ 0 -DarkTol 0.5'
            proc = subprocess.run(aretomo_cmd.split(), capture_output=True, check=True)

            # aretomo is somehow circumventing the `cwd` argument of subprocess.run and dumping everything in the PARENT
            # of the actual cwd. Could not solve, no clue why this happens. So we have to do things differently
            # and move the output around a bit
            imod_dir = ts_dir.parent
            tlt = imod_dir / f'{ts_dir.stem}.aln'
            aln = imod_dir / f'{ts_dir.stem}.tlt'
            xf = imod_dir / f'{ts_dir.stem}.xf'
            xf_warp = f'{ts_name}.mrc.xf'  # needs to be renamed for warp to see it
            shutil.move(tlt, ts_dir)
            shutil.move(aln, ts_dir)
            shutil.move(xf, xf_warp)

            # find any images removed by aretomo cause too dark (should not happen with normalization)
            to_skip = []
            for line in proc.stdout.decode().split('\n'):
                if match := re.search(r'Remove image at (\S+) degree: .*', line):
                    to_skip.append(match)

            if to_skip:
                skipped = True
                warp_dir = ts_list[0].parent.parent
                log = ts_dir / 'aretomo_align.log'
                skipped = "\n".join([match.group() for match in to_skip])
                log.write_text(f'Some images were too dark and were skipped by AreTomo:\n{skipped}\n')
                # flag as disabled in warp
                for match in to_skip:
                    angle = match.group(1)
                    glob = f'{ts_dir.stem}_*_{float(angle):.1f}.xml'
                    xml = list(warp_dir.glob(glob))
                    if len(xml) != 1:
                        warn.append(ts_name)
                        continue
                    xml = xml[0]
                    content = xml.read_text(encoding='utf16')  # warp...
                    replaced = content.replace('UnselectManual="null"', 'UnselectManual="True"')
                    xml.write_text(replaced, encoding='utf16')

    if warn:
        click.secho(f'WARNING: somehow found the wrong number of xml files in {warp_dir}')
        click.secho(f'Check the log and manually disable tilts in Warp for: {", ".join(str(ts)) for ts in warn}.')
    elif skipped:
        click.secho('WARNING: some images were too dark and were skipped by aretomo.')
        click.secho('Warp xml files were automatically updated to reflect these changes by skipping some images!')
