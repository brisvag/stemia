import mrcfile


def read_mrc(path):
    return mrcfile.open(path).data.copy()


def write_mrc(data, path, overwrite=False):
    mrcfile.new(path, data, overwrite=overwrite)
