"""
useful functions for image processing
"""

from math import ceil

import numpy as np
from scipy.ndimage import rotate, label, fourier_shift


def rot_avg(img):
    img_stack = np.zeros((360, *img.shape))
    for i in range(360):
        img_rot = rotate(img, i, reshape=False)
        img_stack[i] = img_rot
    return np.average(img_stack, axis=0)


def crop_center(img, keep, axis='xy'):
    """
    0 < keep < 1
    """
    x, y = img.shape
    startx = 0
    starty = 0
    cropx = x
    cropy = y
    if 'x' in axis:
        cropx = ceil(x * keep)
        startx = x // 2 - (cropx // 2)
    if 'y' in axis:
        cropy = ceil(y * keep)
        starty = y // 2 - (cropy // 2)
    return img[starty:starty+cropy, startx:startx+cropx]


def binarise(img, percentile):
    threshold = np.percentile(img, percentile)
    return np.where(img > threshold, 1, 0)


def to_positive(img):
    return img + img.min()


def fourier_translate(img, shift):
    trans_ft = fourier_shift(np.fft.fftn(img), shift)
    return np.real(np.fft.ifftn(trans_ft)).astype(np.float32)


def label_features(img, kernel=np.ones((3, 3))):
    labeled, count = label(img, structure=kernel)
    return labeled, range(1, count + 1)


def features_by_size(img, kernel=np.ones((3, 3))):
    labeled, count = label_features(img, kernel=kernel)
    by_size = []
    for lb in count:
        feature = np.where(labeled == lb, 1, 0)
        by_size.append(feature)
    by_size.sort(reverse=True, key=lambda feature: feature.sum())
    return labeled, by_size


def rotations(img, degree_range):
    """
    degree range: iterable of degrees (counterclockwise)
    """
    for angle in degree_range:
        yield angle, rotate(img, angle, reshape=False)


def coerce_ndim(img, ndim):
    if img.ndim > ndim:
        raise ValueError(f'image has too high dimensionality ({img.ndim})')
    while img.ndim < ndim:
        img = np.expand_dims(img, 0)
    return img
