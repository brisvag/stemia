import click
import subprocess
from time import sleep
import shutil
import GPUtil
from queue import Queue
from concurrent import futures
from rich.progress import Progress, track
import threading
import math
import os
from pathlib import Path
from rich import print
import contextlib
import pkg_resources

import torch
import torch.nn as nn
from topaz.denoise import UDenoiseNet3D
from topaz.torch import set_num_threads
from topaz.commands.denoise3d import denoise, set_device


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
        if executor._threads == 1:
            task.disable = True

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


def _ccderaser(input, output, cmd='ccderaser', dry_run=False, verbose=False, overwrite=False):
    if not overwrite and output.exists():
        raise FileExistsError(output)
    # run ccderaser, defaults from etomo
    ccderaser_cmd = f'{cmd} -input {input} -output {output} -find -peak 8.0 -diff 6.0 -big 19. -giant 12. -large 8. -grow 4. -edge 4'

    if verbose:
        print(ccderaser_cmd)
    if not dry_run:
        subprocess.run(ccderaser_cmd.split(), capture_output=True, check=True)
    else:
        sleep(0.1)


def fix_batch(tilt_series, cmd='ccderaser', **kwargs):
    if not shutil.which(cmd):
        raise click.UsageError(f'{cmd} is not available on the system')

    partials = [lambda: _ccderaser(ts['stack'], ts['fix'], cmd=cmd, **kwargs) for ts in tilt_series]
    run_threaded(partials, label='Fixing...', **kwargs)


def _aretomo(
    input,
    rawtlt,
    output,
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
    # need to use os.path.relpath cause pathlib cannot handle non-subpath relative paths
    # https://stackoverflow.com/questions/38083555/using-pathlibs-relative-to-for-directories-on-the-same-level
    cwd = output.parent.absolute()
    input = Path(os.path.relpath(input, cwd))
    rawtlt = Path(os.path.relpath(rawtlt, cwd))
    output = Path(os.path.relpath(output, cwd))
    # LogFile is broken, so we do it ourselves
    log = output.with_suffix('.aretomolog')
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
            aln = next(input.parent.glob('*.aln'))
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

    # only one job per gpu
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
    for ts in tilt_series:
        partials.append(
            lambda: _aretomo(
                input=ts['stack' + suffix],
                rawtlt=ts['rawtlt'],
                output=ts['recon' + suffix],
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
    for ts in tilt_series:
        output = ts['stack'].with_stem(ts['stack'].stem + f'_{half}')
        partials.append(lambda: _stack(ts[half], output, cmd=cmd, **kwargs))
    run_threaded(partials, label=f'Stacking {half} halves...', **kwargs)


def _topaz(inputs, output_dir, train=False, even=None, odd=None, cmd='topaz', dry_run=False, verbose=False, overwrite=False):
    # if not overwrite and output_dir.exists():
        # raise FileExistsError(output_dir)

    halves = f'-a {even} -b {odd}' if train else ''
    topaz_cmd = f'{cmd} denoise3d {halves} -o {output_dir} {" ".join(inputs)}'

    if verbose:
        print(topaz_cmd)

    if not dry_run:
        subprocess.run(topaz_cmd.split(), capture_output=True, check=True)
    else:
        sleep(0.1)


def topaz_batch(tilt_series, train=False, cmd='topaz', **kwargs):
    if not shutil.which(cmd):
        raise click.UsageError(f'{cmd} is not available on the system')

    partials = []
    for ts in tilt_series:
        st = ts['stack']
        output = st.parent / 'denoise'
        even = st.with_stem(st.stem + '_even').with_suffix('.mrc')
        odd = st.with_stem(st.stem + '_odd').with_suffix('.mrc')
        partials.append(lambda: _topaz(output, even, odd, cmd=cmd, train=train, **kwargs))
    run_threaded(partials, label='Denoising...', **kwargs)


def topaz_batch(tilt_series, outdir, train=False, dry_run=False, verbose=False, overwrite=False):
    set_num_threads(0)
    model = UDenoiseNet3D(base_width=7)
    f = pkg_resources.resource_stream('topaz', 'pretrained/denoise/unet-3d-10a-v0.2.4.sav')
    state_dict = torch.load(f)
    model.load_state_dict(state_dict)
    model = nn.DataParallel(model)
    model.cuda()

    inputs = [ts['recon'] for ts in tilt_series]

    if verbose:
        print(f'denoising: {inputs[0]} [...] {inputs[-1]}')
        print(f'output: {outdir}')

    if not dry_run:
        for path in track(inputs, 'Denoising...'):
            with contextlib.redirect_stdout(None):
                denoise(
                    model=model,
                    batch_size=torch.cuda.device_count(),
                    path=path,
                    outdir=outdir,
                    suffix='',
                )
