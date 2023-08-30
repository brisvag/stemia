import contextlib
import pkg_resources

from rich import print
import torch
import torch.nn as nn
from topaz.denoise import UDenoiseNet3D
from topaz.torch import set_num_threads
from topaz.commands.denoise3d import denoise


def topaz_batch(progress, tilt_series, outdir, train=False, patch_size=32, dry_run=False, verbose=False, overwrite=False):
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
        for path in progress.track(inputs, description='Denoising...'):
            try:
                with contextlib.redirect_stdout(outdir / 'denoise.log'):
                    denoise(
                        model=model,
                        batch_size=torch.cuda.device_count(),
                        patch_size=patch_size,
                        path=path,
                        outdir=outdir,
                        suffix='',
                    )
            except RuntimeError as e:
                if 'CUDA out of memory.' in e.args[0]:
                    raise RuntimeError('Not enough GPU memory. Try a lower --topaz-patch-size') from e
                raise
