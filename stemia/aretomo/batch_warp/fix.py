import subprocess
from time import sleep
import shutil

from rich import print

from .threaded import run_threaded


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


def fix_batch(progress, tilt_series, cmd='ccderaser', **kwargs):
    if not shutil.which(cmd):
        raise FileNotFoundError(f'{cmd} is not available on the system')

    partials = [lambda ts=ts: _ccderaser(ts['stack'], ts['fix'], cmd=cmd, **kwargs) for ts in tilt_series]
    run_threaded(progress, partials, label='Fixing', **kwargs)
