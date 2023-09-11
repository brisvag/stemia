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


def normalize(img, axes=None, inplace=False):
    """Normalize images to std=1 and mean=0 and dtype float32."""
    img = img.astype(np.float32, copy=not (inplace and img.flags.writeable))
    img -= img.mean(axis=axes, keepdims=True)
    img /= img.std(axis=axes, keepdims=True)
    return img


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


def rotations(img, degree_range, center=None):
    """Generate a number of rotations from an image and a list of angles.

    degree range: iterable of degrees (counterclockwise).
    """
    from skimage.transform import rotate

    if center is None:
        center = np.array(img.shape) // 2

    for angle in degree_range:
        if np.isrealobj(img):
            yield angle, rotate(img, angle, center=center)
        else:
            real = rotate(img.real, angle, center=center)
            imag = rotate(img.imag, angle, center=center)
            yield angle, real + (1j * imag)


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


def rotated_projections(img, healpix_order=2, dtype=None):
    """Generate rotated projections of a map."""
    import healpy
    import numpy as np
    from morphosamplers.sampler import sample_subvolumes
    from numpy.fft import fftn, fftshift, ifftn, ifftshift
    from scipy.spatial.transform import Rotation

    # TODO: sinc function to avoid edge artifacts
    if dtype is not None:
        img = img.astype(dtype)

    ft = fftshift(fftn(fftshift(img)))

    nside = healpy.order2nside(healpix_order)
    npix = healpy.nside2npix(nside)
    # only half the views are needed, cause projection symmetry
    angles = healpy.pix2ang(nside, np.arange(npix // 2))
    angles = np.stack(angles).T
    rot = Rotation.from_euler("xz", angles)
    pos = np.array(ft.shape) / 2
    # get an even size grid that ensures we include everything
    grid_size = int(np.ceil(np.linalg.norm(ft.shape)))
    grid_size += grid_size % 2
    grid_shape = (grid_size, grid_size, 1)
    slices = sample_subvolumes(
        ft, positions=pos, orientations=rot, grid_shape=grid_shape
    ).squeeze()

    return ifftshift(
        ifftn(ifftshift(slices, axes=(1, 2)), axes=(1, 2)), axes=(1, 2)
    ).real


def gaussian_window(shape, sigmas=1):
    """Generate a gaussian_window of the given shape and sigmas."""
    from functools import reduce
    from operator import mul

    from scipy.signal.windows import gaussian

    sigmas = np.broadcast_to(sigmas, len(shape))
    windows = [gaussian(n, s) for n, s in zip(shape, sigmas)]
    return reduce(mul, np.ix_(*windows))


def fourier_resize(img, target_shape, axes=None):
    """Bin or unbin image(s) by fourier cropping or padding."""
    from numpy.fft import fftn, fftshift, ifftn, ifftshift

    if axes is None:
        axes = tuple(range(img.ndim))

    ft = fftshift(fftn(img, axes=axes), axes=axes)

    target_shape = np.array(target_shape)
    if np.all(target_shape <= img.shape):
        edge_crop = ((img.shape - target_shape) // 2).astype(int)
        crop_slice = tuple(
            slice(edge_crop[ax], -edge_crop[ax]) if ax in axes else slice(None)
            for ax in range(img.ndim)
        )
        ft_resized = ft[crop_slice]
        cropped_shape = np.array(ft_resized.shape)
        # needed for edge artifacts
        window = gaussian_window(cropped_shape, cropped_shape / 5)
        ft_resized *= window
    elif np.all(target_shape >= img.shape):
        edge_pad = ((target_shape - img.shape) // 2).astype(int)
        padding = tuple(
            (edge_pad[ax], edge_pad[ax]) if ax in axes else (0, 0)
            for ax in range(img.ndim)
        )
        ft_resized = np.pad(ft, padding)
    else:
        raise NotImplementedError("cannot pad and crop at the same time")

    return ifftn(ifftshift(ft_resized, axes=axes), axes=axes).real


def rescale(img, px_size_in, px_size_out, axes=None):
    """Rescale an image given before/after pixel sizes."""
    ratio = px_size_in / px_size_out
    target_shape = np.round(np.array(img.shape) * ratio / 2) * 2
    return fourier_resize(img, target_shape, axes=axes)


def match_px_size(img1, img2, px_size1, px_size2, axes=None):
    """Match two images' pixel sizes by binning the one with higher resolution."""
    ratio = px_size1 / px_size2
    if ratio > 1:
        return img1, rescale(img2, px_size2, px_size1, axes=axes), px_size1
    else:
        return rescale(img1, px_size1, px_size2, axes=axes), img2, px_size2


def cumsum_nD(img, axes=None):
    """Calculate ndimensional cumsum."""
    axes = list(range(img.ndim)) if axes is None else list(axes)
    out = img.cumsum(axes[0])
    for ax in axes[1:]:
        np.cumsum(out, axis=ax, out=out)
    return out


def correlate_rotations(img, features, angle_step=5):
    """Fast cross correlation of all elements of features and the images.

    Performs also rotations. Input fts must be fftshifted+fftd+fftshifted.
    """
    from numpy.fft import fftn, fftshift, ifftn, ifftshift

    features = coerce_ndim(features, 3)

    shape1 = np.array(img.shape[1:])
    shape2 = np.array(features.shape[1:])

    edges = (np.abs(shape1 - shape2) // 2).astype(int)
    center_slice = tuple(slice(e, -e) if e else slice(None) for e in edges)

    if np.all(shape1 >= shape2):
        img = img[center_slice]
    elif np.all(shape1 <= shape2):
        features = features[:, *center_slice]
    else:
        raise ValueError("weird shapes")

    img = normalize(img, inplace=True)
    features = normalize(features, axes=(1, 2), inplace=True)

    img_ft = fftshift(fftn(fftshift(img)))
    feat_fts = fftshift(fftn(fftshift(features, axes=(1, 2)), axes=(1, 2)), axes=(1, 2))

    img_ft_conj = img_ft.conj()
    img_autocc = np.abs(ifftshift(ifftn(ifftshift(img_ft * img_ft_conj))))
    feat_autocc = np.abs(
        ifftshift(
            ifftn(ifftshift(feat_fts * feat_fts.conj(), axes=(1, 2)), axes=(1, 2)),
            axes=(1, 2),
        )
    )
    norm_denominators = np.sqrt(img_autocc.max() * feat_autocc.max(axis=(1, 2)))

    for feat_ft, denom in zip(feat_fts, norm_denominators):
        best_cc = 0
        for _, feat_ft_rot in rotations(feat_ft, range(0, 360, angle_step)):
            cc_ft = img_ft_conj * feat_ft_rot

            cc = np.abs(ifftshift(ifftn(ifftshift(cc_ft))))

            best_cc = max(np.max(cc / denom), best_cc)
        yield best_cc
