import click
import subprocess
import re
import shutil
import GPUtil
import mrcfile
from queue import Queue
from concurrent import futures


def outputs_exist(ts_dirs, ext, error=False):
    if not isinstance(ext, tuple):
        ext = (ext,)
    for ts_dir in ts_dirs:
        for ex in ext:
            file = ts_dir / (ts_dir.name + ex)
            if file.exists():
                if error:
                    raise FileExistsError(f'{file} already exists; use -f/--overwrite to overwrite any existing files')
                return True
    return False


def get_stem(path):
    if path is not None:
        return path.stem
    return ''


def _ccderaser(input, cmd='ccderaser'):
    fixed = input.with_suffix('.fixed')
    # run ccderaser, defaults from etomo
    ccderaser_cmd = f'{cmd} -input {input} -output {fixed} -find -peak 8.0 -diff 6.0 -big 19. -giant 12. -large 8. -grow 4. -edge 4'
    subprocess.run(ccderaser_cmd.split(), capture_output=True, check=True)


def run_fix(ts_dirs, overwrite, in_ext, cmd='ccderaser'):
    if not shutil.which(cmd):
        raise click.UsageError('ccderaser is not available on the system')
    if not overwrite:
        outputs_exist(ts_dirs, '.fixed', error=True)
    with futures.ThreadPoolExecutor() as executor:
        jobs = []
        for ts_dir in ts_dirs:
            input = ts_dir / (ts_dir.name + in_ext)
            jobs.append(executor.submit(_ccderaser, input, cmd=cmd))
        with click.progressbar(length=len(ts_dirs), label='Fixing...') as bar:
            for job in futures.as_completed(jobs):
                bar.update(1)


def _normalize(input):
    normalized = input.with_suffix('.norm')
    # normalize to mean 0 and stdev 1
    with (
        mrcfile.open(input) as mrc,
        mrcfile.new(normalized, overwrite=True) as mrc_norm
    ):
        mrc_norm.set_data((mrc.data - mrc.data.mean()) / mrc.data.std())


def run_normalize(ts_dirs, overwrite, in_ext):
    if not overwrite:
        outputs_exist(ts_dirs, '.norm', error=True)
    with futures.ThreadPoolExecutor() as executor:
        jobs = []
        for ts_dir in ts_dirs:
            input = ts_dir / (ts_dir.name + in_ext)
            jobs.append(executor.submit(_normalize, input))
        with click.progressbar(length=len(ts_dirs), label='Normalizing...') as bar:
            for job in futures.as_completed(jobs):
                bar.update(1)


def _aretomo(
    input,
    cmd='AreTomo',
    gpu=0,
    tilt_axis=0,
    patches=0,
    thickness_align=1200,
    thickness_recon=0,
    binning=4,
    px_size=0,
    kv=0,
    dose=0,
    cs=0,
    defocus=0,
):
    output = input.with_suffix('.aligned')
    rawtlt = input.with_suffix('.rawtlt')
    log = input.with_suffix('.log')
    cwd = output.parent.absolute()
    options = {
        'InMrc': input.relative_to(cwd),
        'OutMrc': output.relative_to(cwd),
        'AngFile': rawtlt.relative_to(cwd),
        # 'LogFile': log.relative_to(cwd),  # currently broken
        'TiltAxis': tilt_axis or 0,
        'Patch': f'{patches} {patches}',
        'AlignZ': thickness_align,
        'VolZ': thickness_recon,
        'OutBin': binning,
        'PixSize': px_size,
        'Kv': kv,
        'ImgDose': dose,
        'Cs': cs,
        'Defoc': defocus,
        'Gpu': gpu,
        'OutXF': 1,
        'TiltCor': 1,
        'FlipVol': 1,
        'DarkTol': 0,
    }
    # run aretomo with basic settings
    aretomo_cmd = f"{cmd} {' '.join(f'-{k} {v}' for k, v in options.items())}"
    proc = subprocess.run(aretomo_cmd.split(), capture_output=True, check=False, cwd=cwd)
    log.write_bytes(proc.stdout + proc.stderr)


def _aretomo_queue(*args, gpu_queue=None, **kwargs):
    gpu = gpu_queue.get()
    try:
        _aretomo(*args, **kwargs, gpu=gpu)
    finally:
        gpu_queue.put(gpu)


def run_align(ts_dict, overwrite, in_ext, **aretomo_kwargs):
    gpus = [gpu.id for gpu in GPUtil.getGPUs()]
    if not gpus:
        raise click.UsageError('you need at least one GPU to run AreTomo')
    click.secho(f'Running AreTomo in parallel on {len(gpus)} GPUs.')
    # use a queue to hold gpu ids to ensure we only run one job per gpu
    gpu_queue = Queue()
    for gpu in gpus:
        gpu_queue.put(gpu)

    if not overwrite:
        outputs_exist((ts['dir'] for ts in ts_dict.values()), ('.aligned', '.xf'), error=True)

    warn = []
    skipped = False
    with futures.ThreadPoolExecutor(len(gpus)) as executor:
        jobs = []
        for ts_name, ts_data in ts_dict:
            input = ts_data['dir'] / (ts_name + in_ext)
            jobs.append(executor.submit(_aretomo_queue, input, **aretomo_kwargs, **ts_data['aretomo_kwargs'], gpu_queue=gpu_queue))
        with click.progressbar(length=len(ts_dict), label='Aligning...') as bar:
            for job in futures.as_completed(jobs):
                bar.update(1)

            # # aretomo is somehow circumventing the `cwd` argument of subprocess.run and dumping everything in the PARENT
            # # of the actual cwd. Could not solve, no clue why this happens. So we have to do things differently
            # # and move the output around a bit
            # imod_dir = ts_dir.parent
            # tlt = imod_dir / f'{ts_dir.stem}.aln'
            # aln = imod_dir / f'{ts_dir.stem}.tlt'
            # xf = imod_dir / f'{ts_dir.stem}.xf'
            # xf_warp = f'{ts_name}.mrc.xf'  # needs to be renamed for warp to see it
            # shutil.move(tlt, ts_dir)
            # shutil.move(aln, ts_dir)
            # shutil.move(xf, xf_warp)

            # # find any images removed by aretomo cause too dark (should not happen with normalization)
            # to_skip = []
            # for line in proc.stdout.decode().split('\n'):
                # if match := re.search(r'Remove image at (\S+) degree: .*', line):
                    # to_skip.append(match)

            # if to_skip:
                # skipped = True
                # warp_dir = ts_dirs[0].parent.parent
                # log = ts_dir / 'aretomo_align.log'
                # skipped = "\n".join([match.group() for match in to_skip])
                # log.write_text(f'Some images were too dark and were skipped by AreTomo:\n{skipped}\n')
                # # flag as disabled in warp
                # for match in to_skip:
                    # angle = match.group(1)
                    # glob = f'{ts_dir.stem}_*_{float(angle):.1f}.xml'
                    # xml = list(warp_dir.glob(glob))
                    # if len(xml) != 1:
                        # warn.append(ts_name)
                        # continue
                    # xml = xml[0]
                    # content = xml.read_text(encoding='utf16')  # warp...
                    # replaced = content.replace('UnselectManual="null"', 'UnselectManual="True"')
                    # xml.write_text(replaced, encoding='utf16')

    # if warn:
        # click.secho(f'WARNING: somehow found the wrong number of xml files in {warp_dir}')
        # click.secho(f'Check the log and manually disable tilts in Warp for: {", ".join(str(ts)) for ts in warn}.')
    # elif skipped:
        # click.secho('WARNING: some images were too dark and were skipped by aretomo.')
        # click.secho('Warp xml files were automatically updated to reflect these changes by skipping some images!')
