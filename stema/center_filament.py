from pathlib import Path
import warnings

import numpy as np
from scipy.spatial.distance import cdist
from skimage.morphology import skeletonize, remove_small_objects
import mrcfile
import click


from .functions import (
    binarise,
    to_positive,
    label_features,
    features_by_size,
    fourier_translate,
)


def center_filament(img, n_filaments=2, percentile=85):
    binarised = binarise(to_positive(img), percentile)
    labeled, by_size = features_by_size(binarised)
    threshold = by_size[n_filaments - 1].sum()
    clean = remove_small_objects(labeled, min_size=threshold)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=UserWarning)
        skel = skeletonize(clean, method='lee')

    # find centroid of all the "centers" of the filaments
    skel_labeled, count = label_features(skel)
    centers = []
    center = np.array(img.shape) / 2
    for lb in count:
        feature_indexes = np.stack(np.where(skel_labeled == lb), axis=1)
        closest = cdist(feature_indexes, [center]).argmin()
        centers.append(feature_indexes[closest])
    centroid = np.stack(centers).mean(axis=0)

    # translate image
    shift = center - centroid
    trans = fourier_translate(img, shift)
    return trans


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('input', type=click.Path(exists=True, dir_okay=False))
@click.argument('output', type=click.Path(dir_okay=False), required=False)
@click.option('-f', '--overwrite', is_flag=True, help='overwrite output if exists')
@click.option('-n', '--n-filaments', default=2, help='number of filaments on the image')
@click.option('-p', '--percentile', default=85, help='percentile for binarisation')
def main(input, output, n_filaments, percentile, overwrite):
    """
    Center an mrc image containing filament(s).

    If OUTPUT is not given, default to INPUT_centered.mrc
    """
    # don't waste time processing if overwrite is off and output exists
    output = output or Path(input).stem + '_centered.mrc'
    if Path(output).is_file() and not overwrite:
        raise click.UsageError(f'{output} exists but "-f" flag was not passed')

    imgs = mrcfile.open(input).data.copy()

    if imgs.ndim == 2:
        imgs = [imgs]

    out = []
    failed = []
    with click.progressbar(imgs, label='Processing image slices') as images:
        # ugly counter to keep progressbar functionality
        i = 0
        for img in images:
            try:
                centered = center_filament(img, n_filaments, percentile)
            except IndexError:
                failed.append(i)
                centered = img
            out.append(centered)
            i += 1

    if len(out) == 1:
        out_img = out[0]
    else:
        out_img = np.stack(out)

    if failed:
        click.secho(f'WARNING: could not {n_filaments} filaments in the following images:\n'
                    f'{failed}\nWill leave as is!', fg='red')

    mrcfile.new(output, out_img, overwrite=overwrite)
