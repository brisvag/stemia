import click
import subprocess
from time import sleep
import shutil
import GPUtil
from queue import Queue
from concurrent import futures
from itertools import product
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
        errors = []
        for job in futures.as_completed(jobs):
            try:
                job.result()
            except FileExistsError:
                exist += 1
            except subprocess.CalledProcessError as e:
                errors.append(e)
            bar.update(main_task, advance=1)

        for t in bar.tasks:
            t.completed = t.total

        if exist:
            print(f'[red]{exist} files already existed and were not overwritten')

        if errors:
            print(f'[red]{len(errors)} commands have failed:')
            for err in errors:
                print(f'[yellow]{" ".join(err.cmd)}[\yellow] failed with:\n[red]{err.stderr.decode()}')


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


def _aretomo(
    input,
    suffix='',
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
    rawtlt = input.with_stem(input.stem.removesuffix(suffix)).with_suffix('.rawtlt').relative_to(cwd)
    output = input.with_suffix('.mrc').relative_to(cwd)
    # LogFile is broken, so we do it ourselves
    log = input.with_suffix('.aretomolog').relative_to(cwd)
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
        try:
            aln = next(cwd.glob('*.aln'))
        except StopIteration:
            raise FileNotFoundError('could not find aln file')
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
            log.write_bytes(proc.stdout + proc.stderr)
            if gpu_queue is not None:
                gpu_queue.put(gpu)
            proc.check_returncode()
    else:
        sleep(0.1)


def aretomo_batch(tilt_series, suffix='', label='Aligning...', cmd='AreTomo', **kwargs):
    if not shutil.which(cmd):
        raise click.UsageError(f'{cmd} is not available on the system')
    gpus = [gpu.id for gpu in GPUtil.getGPUs()]
    if not gpus:
        raise click.UsageError('you need at least one GPU to run AreTomo')
    if kwargs.get('verbose'):
        print(f'[yellow]Running AreTomo in parallel on {len(gpus)} GPUs.')

    # use a queue to hold gpu ids to ensure we only run one job per gpu
    gpu_queue = Queue()
    for gpu in gpus:
        gpu_queue.put(gpu)

    partials = []
    for ts in tilt_series.values():
        input = ts['stack'].with_stem(ts['stack'].stem + suffix)
        partials.append(
            lambda: _aretomo(
                input=input,
                suffix=suffix,
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
        short_cmd = f'{cmd} {images[0]} [...] {images[-1]} {output}'
        print(short_cmd)

    if not dry_run:
        subprocess.run(stack_cmd.split(), capture_output=True, check=True)
    else:
        sleep(0.1)


def prepare_half_stacks(tilt_series, half, cmd='newstack', **kwargs):
    if not shutil.which(cmd):
        raise click.UsageError(f'{cmd} is not available on the system')

    partials = []
    for ts in tilt_series.values():
        output = ts['stack'].with_stem(ts['stack'].stem + f'_{half}')
        partials.append(lambda: _stack(ts[half], output, cmd=cmd, **kwargs))
    run_threaded(partials, label=f'Stacking {half} halves...', **kwargs)
