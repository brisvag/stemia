import shutil
import subprocess
from time import sleep

from rich import print

from .threaded import run_threaded


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


def prepare_half_stacks(progress, tilt_series, half, cmd='newstack', **kwargs):
    if not shutil.which(cmd):
        raise FileNotFoundError(f'{cmd} is not available on the system')

    partials = [
        lambda ts=ts: _stack(ts[half], ts[f'stack_{half}'], cmd=cmd, **kwargs)
        for ts in tilt_series
    ]
    run_threaded(progress, partials, label=f'Stacking {half} halves', **kwargs)
