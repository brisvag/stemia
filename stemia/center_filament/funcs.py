import warnings

import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from skimage.morphology import skeletonize, remove_small_objects
import click


from ..utils.image_processing import (
    binarise,
    to_positive,
    label_features,
    features_by_size,
    fourier_translate,
    rotations,
    crop_center,
)


def _center_filament(img, n_filaments=2, percentile=85):
    """
    center an image containing one or more filaments, and rotate it vertically
    percentile: used for binarisation
    """
    dtype = img.dtype
    binarised = binarise(to_positive(img), percentile)
    labeled, by_size = features_by_size(binarised)
    threshold = by_size[n_filaments - 1].sum()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', category=UserWarning)
        clean = remove_small_objects(labeled, min_size=threshold)
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

    # find best rotation
    best_rot = None
    best_peak = -1000
    best_angle = 0
    for angle, img_rot in rotations(trans, range(-90, 91)):
        rot_crop = crop_center(img_rot, 0.3, axis='y')
        parts = np.split(rot_crop, n_filaments, axis=1)     # may break with n > 3 and non-even spacing
        peaks = [part.sum(axis=0).max() for part in parts]
        peak = sum(peaks)
        peak = rot_crop.sum(axis=0).max()
        if peak > best_peak:
            best_rot = img_rot
            best_angle = angle
            best_peak = peak

    # back to original type?
    best_rot = best_rot.astype(dtype)

    return best_rot, shift, best_angle


def center_filaments(imgs, n_filaments=2, percentile=85):
    out_imgs = []
    shifts = []
    angles = []
    failed = []
    with click.progressbar(enumerate(imgs), label='Processing image slices...', length=len(imgs)) as images:
        for i, img in images:
            try:
                centered, shift, angle = _center_filament(img, n_filaments, percentile)
            except IndexError:
                failed.append(i)
                centered = img
                shift = np.array([0, 0])
                angle = 0
            out_imgs.append(centered)
            shifts.append(shift)
            angles.append(angle)

    out_imgs = np.squeeze(np.stack(out_imgs))

    if failed:
        click.secho(f'WARNING: could not find {n_filaments} filaments in the following images:\n'
                    f'{failed}\nWill leave as is!', fg='red')

    return out_imgs, shifts, angles


def update_starfile(df, shifts, angles, optics):
    click.secho('Updating particle positions...')
    x_shift, y_shift = np.stack(shifts).T
    if optics is not None:
        px_size = optics['rlnImagePixelSize'][0]
        x_shift /= px_size
        y_shift /= px_size
    df_transform = pd.DataFrame({'cf_x_shift': x_shift, 'cf_y_shift': y_shift, 'cf_rot': angles})
    df_transform.index.name = 'rlnClassNumber'
    df_transform.index += 1
    merged = df.merge(df_transform, on='rlnClassNumber')
    df['rlnOriginXAngst'] += merged['cf_x_shift']
    df['rlnOriginYAngst'] += merged['cf_y_shift']
    df['rlnAnglePsi'] += merged['cf_rot']

    return df
