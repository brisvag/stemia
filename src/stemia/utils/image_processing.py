"""useful functions for image processing."""

from math import ceil

import numpy as np


def rot_avg(img):
    """Calculate the rotational average of an image."""
    from scipy.ndimage import rotate

    img_stack = np.zeros((360, *img.shape))
    for i in range(360):
        img_rot = rotate(img, i, reshape=False)
        img_stack[i] = img_rot
    return np.average(img_stack, axis=0)


def crop_center(img, keep, axis="xy"):
    """Crop anything but the center, keeping keep*shape."""
    x, y = img.shape
    startx = 0
    starty = 0
    cropx = x
    cropy = y
    if "x" in axis:
        cropx = ceil(x * keep)
        startx = x // 2 - (cropx // 2)
    if "y" in axis:
        cropy = ceil(y * keep)
        starty = y // 2 - (cropy // 2)
    return img[starty : starty + cropy, startx : startx + cropx]


def binarise(img, percentile):
    """Binarise an image given a percentile threshold."""
    threshold = np.percentile(img, percentile)
    return np.where(img > threshold, 1, 0)


def to_positive(img):
    """Positivize an image."""
    return img + img.min()


def fourier_translate(img, shift):
    """Translate an image with fourier_shift."""
    from scipy.ndimage import fourier_shift

    trans_ft = fourier_shift(np.fft.fftn(img), shift)
    return np.real(np.fft.ifftn(trans_ft)).astype(np.float32)


def label_features(img, kernel=None):
    """Generate image labels given a certain kernel."""
    from scipy.ndimage import label

    labeled, count = label(
        img, structure=kernel if kernel is not None else np.ones((3, 3))
    )
    return labeled, range(1, count + 1)


def features_by_size(img, kernel=None):
    """Sort features by size in an image by labeling it."""
    labeled, count = label_features(
        img, kernel=kernel if kernel is not None else np.ones((3, 3))
    )
    by_size = []
    for lb in count:
        feature = np.where(labeled == lb, 1, 0)
        by_size.append(feature)
    by_size.sort(reverse=True, key=lambda feature: feature.sum())
    return labeled, by_size


def rotations(img, degree_range):
    """Generate a number of rotations from an image and a list of angles.

    degree range: iterable of degrees (counterclockwise).
    """
    from scipy.ndimage import rotate

    for angle in degree_range:
        yield angle, rotate(img, angle, reshape=False)


def coerce_ndim(img, ndim):
    """Coerce image dimensionality if smaller than ndim."""
    if img.ndim > ndim:
        raise ValueError(f"image has too high dimensionality ({img.ndim})")
    while img.ndim < ndim:
        img = np.expand_dims(img, 0)
    return img


def compute_dist_field(shape, field_type, center=None, axis=None, threshold=None):
    """Compute a distance field for a give nd-image."""
    if center is None:
        center = np.array(shape) / 2

    ndim = len(shape)

    ranges = [np.arange(0, d) for d in shape]
    indices = np.stack(np.meshgrid(*ranges, indexing="ij"), axis=-1) + 0.5

    if field_type == "sphere":
        dists = np.linalg.norm(indices - center, axis=-1)
    elif field_type == "cylinder":
        line = np.full((shape[axis], ndim), center)
        line[:, axis] = np.arange(shape[axis])
        new_shape = [1 for _ in shape] + [ndim]
        new_shape[axis] = -1
        line = line.reshape(new_shape)
        dists = np.linalg.norm(indices - line, axis=-1)
    elif field_type == "threshold":
        import edt
        import mrcfile

        with mrcfile.open(input, permissive=True) as mrc:
            data = mrc.data
        binarized = data > threshold
        dists = -edt.sdf(binarized)

    return dists


def smoothstep_normalized(arr, min_val, max_val):
    """Normalized smoothstep function (0, 1)."""
    rng = max_val - min_val
    normalized = (arr - min_val) / rng
    smooth = np.where(
        normalized < 0,
        0,
        np.where(normalized <= 1, 3 * normalized**2 - 2 * normalized**3, 1),
    )
    return 1 - smooth


def create_mask_from_field(field, radius, inner_radius=None, padding=None):
    """Generate a mask given a distance field and a radius + padding."""
    mask = smoothstep_normalized(field, radius, radius + padding)
    if inner_radius is not None:
        inner_mask = smoothstep_normalized(field, inner_radius, inner_radius + padding)
        mask -= inner_mask

    return mask
