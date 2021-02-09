#!/usr/bin/env python3

"""
center an mrc image containing filament(s)
"""

from argparse import ArgumentParser
from pathlib import Path
import sys

import numpy as np
from scipy.spatial.distance import cdist
from skimage.morphology import skeletonize, remove_small_objects
import mrcfile


from .functions import (
    binarise,
    to_positive,
    label_features,
    features_by_size,
    fourier_translate,
)


def center_filament(img, n_filaments=2, percentile=85):
    binarised = binarise(to_positive(img), percentile)
    labeled, sizes = features_by_size(binarised)
    threshold = sizes[-n_filaments]
    clean = remove_small_objects(labeled, min_size=threshold)
    skel = skeletonize(clean, method='lee')

    # find centroid of all the "centers" of the filaments
    skel_labeled, count = label_features(skel)
    centers = []
    center = np.array(img.shape) / 2
    for lb in count:
        feature_indexes = np.stack(np.where(skel_labeled == lb), axis=0)
        closest = cdist(feature_indexes, [center]).argmin()
        centers.append(feature_indexes[closest])
    centroid = np.stack(centers).mean(axis=0)

    # translate image
    shift = center - centroid
    trans = fourier_translate(img, shift)
    return trans


def main(img_path, output_path, n_filaments, percentile, overwrite):
    imgs = mrcfile.open(img_path).data.copy()

    if imgs.ndim == 2:
        imgs = [imgs]

    out = []
    for img in imgs:
        centered = center_filament(img, n_filaments, percentile)
        out.append(centered)

    if len(out) == 1:
        out_img = out[0]
    else:
        out_img = np.stack(out)

    mrcfile.new(output_path, out_img, overwrite=overwrite)


def parse():
    parser = ArgumentParser(prog='center_filament')
    parser.add_argument('input', type=Path, help='image file to center')
    parser.add_argument('output', type=Path, nargs='?', help='output file name. By default, input_centered.mrc')
    parser.add_argument('-f', '--force-overwrite', action='store_true', help='overwrite output if exists')
    parser.add_argument('-n', '--n-filaments', type=int, default=2, help='number of filaments on the image')
    parser.add_argument('-p', '--percentile', type=int, default=2, help='percentile for binarisation')

    args = parser.parse_args(sys.argv[1:])
    if not args.input.is_file():
        parser.error(f'{args.input} does not exist')
    if not args.output:
        args.output = Path(args.input.stem + '_centered.mrc')
    if args.output.is_file() and not args.force_overwrite:
        parser.error(f'{args.output} exists. Use -f to overwrite')
    return args


if __name__ == '__main__':
    args = parse()
    main(args.input, args.output, args.n_filaments, args.percentile, args.overwrite)
