import sys
import numpy as np
import pandas as pd
import json
from pathlib import Path


def find_cs_files(job_dir):
    with open(job_dir / 'job.json', 'r') as f:
        job = json.load(f)

    files = {
        'particles': {
            'cs': set(),
            'passthrough': set(),
        },
        'micrographs': {
            'cs': set(),
            'passthrough': set(),
        },
    }
    for output in job['output_results']:
        passthrough = output['passthrough']
        for file in output['metafiles']:
            if 'excluded' in file:
                continue

            if 'particles' in file:
                k1 = 'particles'
            elif 'micrographs' in file:
                k1 = 'micrographs'
            else:
                continue

            if passthrough:
                k2 = 'passthrough'
            else:
                k2 = 'cs'

            files[k1][k2].add(job_dir.parent / file)

    for dct in files.values():
        for k in dct:
            dct[k] = sorted(dct[k])[-1] if dct[k] else None

    def update(d1, d2):
        for k1, v in d1.items():
            for k2 in v:
                if d1[k1][k2] is None:
                    d1[k1][k2] = d2[k1][k2]

    for parent in job['parents']:
        update(files, find_cs_files(job_dir.parent / parent))
        if all(f is not None for dct in files.values() for file in dct.values()):
            break

    return files


def read_cs_file(cs_file):
    data = np.load(cs_file)
    df = pd.DataFrame(data.tolist(), columns=data.dtype.names)
    cols = []
    for col in df.columns:
        # check first element for the rest
        el = df[col].iloc[0]
        if isinstance(el, np.ndarray):
            # split columns and add index at the end (e.g: pose_0, pose_1, pose_2)
            split_col = pd.DataFrame(
                df[col].tolist(),
                columns=[f'{col}_{i}' for i in range(len(el))]
            )
            cols.append(split_col)
        elif isinstance(el, bytes):
            cols.append(df[col].str.decode('utf-8'))
        else:
            cols.append(df[col])
    # stitch them back together
    df = pd.concat(cols, axis=1)
    return df


def load_job_data(job_dir):
    """
    Read a cryosparc job directory into a pandas dataframe

    Returns a merged dataframe.
    """
    job_dir = Path(job_dir).resolve().absolute()
    files = find_cs_files(job_dir)

    particles = [file for file in files['particles'].values() if file is not None]
    micrographs = [file for file in files['micrographs'].values() if file is not None]
    if not particles and not micrographs:
        sys.exit()

    part_data = [read_cs_file(part) for part in particles]
    mic_data = [read_cs_file(mic) for mic in micrographs]
    for mic in mic_data:
        mic.rename(columns={'uid': 'location/micrograph_uid'}, inplace=True)

    df = None
    if len(part_data) == 2:
        df = pd.merge(part_data[0], part_data[1], on='uid')
    elif len(part_data) == 1:
        df = part_data[0]

    if mic_data:
        mcs = iter(mic_data)
        if df is None:
            df = next(mcs)
        for mc in mcs:
            df = df.merge(mc, on='location/micrograph_uid')

    return df
