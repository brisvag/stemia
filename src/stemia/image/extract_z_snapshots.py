import click


@click.command()
@click.argument('inputs', nargs=-1, type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-o', '--output-dir', default='./snapshots', type=click.Path(dir_okay=True, resolve_path=True))
@click.option('-n', '--n-slices', default=5, type=int, help='number of equidistant slices to extract')
@click.option('--keep-extrema', is_flag=True, help='whether to keep slices at z=0 and z=-1 (if false, slices is reduced by 2)')
@click.option('-a', '--average', default=1, type=int, help='number of slices to average over')
@click.option('-s', '--size', default=None, type=str, help='size of final image (X,Y)')
@click.option('-r', '--range', 'rng', default=None, type=str, help='range of slices to image (A,B)')
@click.option('--axis', default=0, type=int, help='axis along which to do the slicing')
def cli(inputs, output_dir, keep_extrema, n_slices, average, axis, size, rng):
    """
    Grab z slices at regular intervals from a tomogram as jpg images.

    INPUTS: any number of paths of volume images
    """
    if not inputs:
        return

    from scipy.ndimage import convolve
    import napari
    import numpy as np
    import cryohub
    from cryotypes.image import ImageProtocol
    from pathlib import Path
    from rich.progress import Progress

    out = Path(output_dir)
    data = [i for i in cryohub.read(*inputs) if isinstance(i, ImageProtocol)]
    if not data:
        return

    out.mkdir(parents=True, exist_ok=True)
    v = napari.Viewer()
    with Progress() as progress:
        for d in progress.track(data, description='Processing inputs'):
            img = np.moveaxis(d.data, axis, 0)
            if average > 1:
                avg_weights = np.ones((average, 1, 1)) / average
                img = convolve(img, avg_weights)

            v.add_image(img, interpolation2d='spline36')

            if size is not None:
                size = [int(s) for s in size.split(',')]
            else:
                size = img.shape[1:]

            v.window._qt_viewer.canvas.size = size
            v.reset_view()
            v.camera.zoom *= 1.2

            steps = list(range(1 - int(keep_extrema), n_slices + 1 + int(keep_extrema)))
            if rng is not None:
                start, end = [int(sl) for sl in rng.split(',')]
                step_size = (end - start) / (n_slices + 1)
            else:
                start = 0
                step_size = len(img) / (n_slices + 1)
            for i in progress.track(steps, description='Generating slices'):
                idx = start + int(i * step_size)
                v.dims.set_current_step(0, idx)

                save_as = out / (d.source.stem + f'_slice_{idx:03}.png')
                v.screenshot(save_as, size=size, canvas_only=True)

            v.layers.clear()
