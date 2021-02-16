import pandas as pd
import mrcfile
import starfile


def read_mrc(path):
    with mrcfile.open(path) as mrc:
        return mrc.data.copy(), mrc.header


def write_mrc(data, path, overwrite=False, from_header=None):
    with mrcfile.new(path, data, overwrite=overwrite) as mrc:
        if from_header is not None:
            mrc.header.cella = from_header.cella


def read_particle_star(path):
    dct = starfile.read(path)
    if isinstance(dct, pd.DataFrame):
        df = dct
        optics = None
    else:
        df = dct['particles']
        optics = dct['optics']
    return df, optics


def write_particle_star(data, path, overwrite=False, optics=None):
    if optics is not None:
        data = {'optics': optics, 'particles': data}
    starfile.write(data, path, overwrite=overwrite)
