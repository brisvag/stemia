import click
import subprocess
from time import sleep
import shutil
import GPUtil
from queue import Queue
from concurrent import futures
from itertools import product
import numpy as np
from rich.progress import Progress
import threading
import math
import os
from rich import print


def run_threaded(partials, label='', max_workers=None, dry_run=False, **kwargs):
    def update_bar(bar, thread_to_task):
        bar.update(thread_to_task[threading.get_ident()], advance=1)

    max_workers = max_workers or min(32, os.cpu_count() + 4)  # see concurrent docs
    thread_to_task = {}

    with (
        Progress(disable=dry_run) as bar,
        futures.ThreadPoolExecutor(max_workers) as executor
    ):
        main_task = bar.add_task(label, total=len(partials))

        jobs = []
        for fn in partials:
            job = executor.submit(fn)
            job.add_done_callback(lambda _: update_bar(bar, thread_to_task))
            jobs.append(job)

        for thread in executor._threads:
            task = bar.add_task('', total=math.ceil(len(partials) / max_workers))
            thread_to_task[thread.ident] = task

        exist = 0
        for job in futures.as_completed(jobs):
            try:
                job.result()
            except FileExistsError:
                exist += 1
            bar.update(main_task, advance=1)

        for t in bar.tasks:
            t.completed = t.total

        if exist:
            print(f'[red]{exist} files already existed and were not overwritten')


def _ccderaser(input, cmd='ccderaser', dry_run=False, verbose=False, overwrite=False):
    fixed = input.with_stem(input.stem + '_fix')
    if not overwrite and fixed.exists():
        raise FileExistsError(fixed)
    # run ccderaser, defaults from etomo
    ccderaser_cmd = f'{cmd} -input {input} -output {fixed} -find -peak 8.0 -diff 6.0 -big 19. -giant 12. -large 8. -grow 4. -edge 4'

    if verbose:
        print(ccderaser_cmd)
    if not dry_run:
        subprocess.run(ccderaser_cmd.split(), capture_output=True, check=True)
    else:
        sleep(0.1)


def fix_batch(tilt_series, cmd='ccderaser', **kwargs):
    if not shutil.which(cmd):
        raise click.UsageError(f'{cmd} is not available on the system')

    partials = [lambda: _ccderaser(ts['stack'], cmd=cmd, **kwargs) for ts in tilt_series.values()]
    run_threaded(partials, label='Fixing...', **kwargs)


# def _normalize(input, in_ext, overwrite=False):
    # normalized = input.with_stem(input.stem.removesuffix(in_ext) + '_norm')
    # if not overwrite and normalized.exists():
        # raise FileExistsError(normalized)
    # # normalize to mean 0 and stdev 1
    # with (
        # mrcfile.open(input) as mrc,
        # mrcfile.new(normalized, overwrite=True) as mrc_norm
    # ):
        # mrc_norm.set_data((mrc.data - mrc.data.mean()) / mrc.data.std())


# def normalize_batch(tilt_series, **kwargs):
    # partials = [lambda: _normalize(ts['stack'], **kwargs) for ts in tilt_series.values()]
    # run_threaded(partials, label='Normalizing...')


def _aretomo(
    input,
    in_ext='',
    out_ext='_aligned',
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
    from_aln=False,
    gpu_queue=None,
    dry_run=False,
    verbose=False,
    overwrite=False,
):
    # cwd dance is necessary cause aretomo messes up paths otherwise
    cwd = input.parent.absolute()
    rawtlt = input.with_stem(input.stem.removesuffix(in_ext)).with_suffix('.rawtlt').relative_to(cwd)
    output = input.with_stem(input.stem.removesuffix(in_ext) + out_ext).with_suffix('.mrc').relative_to(cwd)
    input = input.relative_to(cwd)
    if not overwrite and output.exists():
        raise FileExistsError(output)

    options = {
        'InMrc': input,
        'OutMrc': output,
        # 'LogFile': input.with_suffix('.log').relative_to(cwd),  # currently broken
        'VolZ': thickness_recon,
        'OutBin': binning,
        'PixSize': px_size,
        'Kv': kv,
        'ImgDose': dose,
        'Cs': cs,
        'Defoc': defocus,
        'Gpu': gpu,
        'FlipVol': 1,
        'DarkTol': 0,
    }

    if from_aln:
        # due to a quirk of aretomo, with_suffix is named wrong because all extensions are removed
        # for now, let's just hope a single aln exists
        aln = next(cwd.glob('*.aln'))
        if not aln.exists():
            raise FileNotFoundError(aln)
        options.update({
            # 'AlnFile': input.with_suffix('.aln').relative_to(cwd),
            'AlnFile': aln,
        })
    else:
        options.update({
            'AngFile': rawtlt,
            'AlignZ': thickness_align,
            'TiltAxis': tilt_axis or 0,
            'Patch': f'{patches} {patches}',
            'TiltCor': 1,
            'OutXF': 1,
        })

    # only one job per gpu, to make sure
    if gpu_queue is None:
        gpu = gpu or 0
    else:
        gpu = gpu_queue.get()

    # run aretomo with basic settings
    aretomo_cmd = f"{cmd} {' '.join(f'-{k} {v}' for k, v in options.items())}"

    if verbose:
        print(aretomo_cmd)

    if not dry_run:
        try:
            proc = subprocess.run(aretomo_cmd.split(), capture_output=True, check=False, cwd=cwd)
        finally:
            # LogFile is broken, so we do it ourselves
            log = input.with_suffix('.aretomolog').relative_to(cwd)
            log.write_bytes(proc.stdout + proc.stderr)
            if gpu_queue is not None:
                gpu_queue.put(gpu)
            proc.check_returncode()
    else:
        sleep(0.1)


def aretomo_batch(tilt_series, in_ext='', out_ext='_aligned', label='Aretomoing...', cmd='AreTomo', **kwargs):
    if not shutil.which(cmd):
        raise click.UsageError(f'{cmd} is not available on the system')
    gpus = [gpu.id for gpu in GPUtil.getGPUs()]
    if not gpus:
        raise click.UsageError('you need at least one GPU to run AreTomo')
    print(f'[yellow]Running AreTomo in parallel on {len(gpus)} GPUs.')

    # use a queue to hold gpu ids to ensure we only run one job per gpu
    gpu_queue = Queue()
    for gpu in gpus:
        gpu_queue.put(gpu)

    partials = []
    for ts in tilt_series.values():
        input = ts['stack'].with_stem(ts['stack'].stem + in_ext)
        partials.append(
            lambda: _aretomo(
                input=input,
                in_ext=in_ext,
                out_ext=out_ext,
                gpu_queue=gpu_queue,
                cmd=cmd,
                **ts['aretomo_kwargs'],
                **kwargs,
            )
        )

    run_threaded(partials, label=label, **kwargs)


def _stack(images, output, cmd='newstack', dry_run=False, verbose=False, overwrite=False):
    if not overwrite and output.exists():
        raise FileExistsError(output)
    stack_cmd = f'{cmd} {" ".join(str(img) for img in images)} {output}'

    if verbose:
        print(stack_cmd)

    if not dry_run:
        subprocess.run(stack_cmd.split(), capture_output=True, check=True)
    else:
        sleep(0.1)


def prepare_half_stacks(tilt_series, in_ext, cmd='newstack', **kwargs):
    if not shutil.which(cmd):
        raise click.UsageError(f'{cmd} is not available on the system')

    partials = []
    for ts, half in product(tilt_series.values(), ('even', 'odd')):
        output = ts['stack'].with_stem(ts['stack'].stem.removesuffix(in_ext) + f'_{half}')
        partials.append(lambda: _stack(ts[half], output, cmd=cmd, **kwargs))
    run_threaded(partials, label='Stacking halves...', **kwargs)


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
