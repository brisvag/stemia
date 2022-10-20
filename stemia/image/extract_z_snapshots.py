import click


@click.command()
@click.argument('inputs', nargs=-1, type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-o', '--output-dir', default='./snapshots', type=click.Path(dir_okay=True, resolve_path=True))
@click.option('-s', '--slices', default=5, type=int, help='number of equidistant slices to extract')
@click.option('--keep-extrema', is_flag=True, help='whether to keep slices at z=0 and z=-1 (if false, slices is reduced by 2)')
@click.option('--average', default=1, type=int, help='number of slices to average over')
@click.option('--axis', default=0, type=int, help='axis along which to do the slicing')
def cli(inputs, output_dir, keep_extrema, slices, average, axis):
    """
    Grab z slices at regular intervals from a tomogram as jpg images.

    INPUTS: any number of paths of volume images
    """
    if not inputs:
        return

    from scipy.ndimage import uniform_filter1d
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
                img = uniform_filter1d(img, size=average, axis=0)

            rng = list(range(1 - int(keep_extrema), slices + 1 + int(keep_extrema)))
            step = len(img) / (slices + 1)
            for i in progress.track(rng, description='Generating slices'):
                idx = int(i * step)

                v.add_image(img[idx])
                v.window._qt_viewer.canvas.size = img.shape[1:]
                v.reset_view()
                v.camera.zoom *= 1.2

                save_as = out / (d.source.stem + f'_slice_{idx:03}.png')
                v.screenshot(save_as, size=img.shape[1:], canvas_only=True)
                v.layers.clear()
