import re
import numpy as np
import pandas as pd
import json
from pathlib import Path
import warnings


def update_dict(d1, d2):
    for k1, v in d1.items():
        for k2 in v:
            if not d1[k1][k2]:
                d1[k1][k2].update(d2[k1][k2])


def find_cs_files(job_dir, sets=None):
    """
    Recursively explore a job directory to find all the relevant cs files.

    This function recurses through all the parent jobs until it finds all the files
    required to have all the relevant info about the current job.
    """
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
    job_dir = Path(job_dir).absolute()
    try:
        with open(job_dir / 'job.json', 'r') as f:
            job = json.load(f)
    except FileNotFoundError:
        warnings.warn(f'parent job "{job_dir.name}" is missing or corrupted')
        return files

    j_type = job['type']
    for output in job['output_results']:
        metafiles = output['metafiles']
        passthrough = output['passthrough']
        k2 = 'passthrough' if passthrough else 'cs'
        if j_type == 'hetero_refine':
            # hetero refine is special because the "good" output is split into multiple files
            if (not passthrough and 'particles_class_' in output['group_name']) or (passthrough and output['group_name'] == 'particles_all_classes'):
                files['particles'][k2].add(job_dir.parent / metafiles[-1])
        elif j_type == 'particle_sets':
            if (matched := re.search(r'split_(\d+)', output['group_name'])) is not None:
                if sets is None or int(matched[1]) in [int(s) for s in sets]:
                    files['particles'][k2].add(job_dir.parent / metafiles[-1])
        else:
            # every remaining job type is covered by this generic loop
            for file in metafiles:
                if any(bad in file for bad in ('excluded', 'incomplete', 'remainder', 'rejected', 'uncategorized')):
                    continue
                if 'particles' in file:
                    k1 = 'particles'
                elif 'micrographs' in file:
                    k1 = 'micrographs'
                else:
                    continue

                files[k1][k2].add(job_dir.parent / file)

            for dct in files.values():
                for k in dct:
                    dct[k] = set(sorted(dct[k])[-1:])

    # remove non-existing files
    for dct in files.values():
        for kind, file_set in dct.items():
            for f in list(file_set):
                if not f.exists():
                    warnings.warn(
                        'the following file was supposed to contain relevant information, '
                        f'but does not exist:\n{f}'
                    )
                    file_set.remove(f)

    for parent in job['parents']:
        update_dict(files, find_cs_files(job_dir.parent / parent))
        if all(file_set for dct in files.values() for file_set in dct.values()):
            # found everything we need
            break

    return files


def recarray_to_flat_dataframe(recarray, column_name=None):
    columns = []
    if recarray.dtype.fields is not None:
        for col in recarray.dtype.names:
            data = recarray_to_flat_dataframe(recarray[col], column_name=col)
            columns.append(data)
    elif recarray.ndim == 2:
        for idx, subcolumn in enumerate(recarray.T):
            columns.append(pd.Series(name=f'{column_name}_{idx}', data=subcolumn))
    else:
        columns.append(pd.Series(name=column_name, data=recarray, dtype=recarray.dtype))

    df = pd.concat(columns, axis=1)

    # convert bytes to strings
    for col in df.columns:
        el = df[col].iloc[0]
        if isinstance(el, bytes):
            df[col] = df[col].str.decode('utf-8')

    return df


def read_cs_file(cs_file):
    data = np.load(cs_file)
    # convert dtypes ensure we allow NaN with stuff like integers
    return recarray_to_flat_dataframe(data).convert_dtypes()


def load_job_data(job_dir, particles=True, micrographs=True, drop_na=False):
    """
    Read a cryosparc job directory into a pandas dataframe

    Returns a merged dataframe.
    """
    job_dir = Path(job_dir).resolve().absolute()
    files = find_cs_files(job_dir)

    if not files['particles']['cs'] and not files['micrographs']['cs']:
        return pd.DataFrame()

    part_df = None
    mic_df = None
    df = None

    if particles:
        part_data = [read_cs_file(part) for part in files['particles']['cs']]
        part_passthrough = [read_cs_file(part) for part in files['particles']['passthrough']]

        part_df = pd.concat(part_data, ignore_index=True)
        if part_passthrough:
            for pst in part_passthrough:
                # keep only most recent data (non-passthrough)
                to_drop = [col for col in part_df.columns if not col == 'uid']
                pst.drop(columns=to_drop, errors='ignore', inplace=True)
                part_df = pd.merge(part_df, pst, on='uid', how='outer')

        df = part_df

    if micrographs:
        mic_data = [read_cs_file(mic) for mic in files['micrographs']['cs']]
        mic_passthrough = [read_cs_file(mic) for mic in files['micrographs']['passthrough']]

        mic_df = pd.concat(mic_data, ignore_index=True)
        if mic_passthrough:
            for pst in mic_passthrough:
                # keep only most recent data (non-passthrough)
                to_drop = [col for col in mic_df.columns if not col == 'uid']
                pst.drop(columns=to_drop, errors='ignore', inplace=True)
                mic_df = pd.merge(mic_df, pst, on='uid', how='outer')

        mic_df.rename(columns={'uid': 'location/micrograph_uid'}, inplace=True)

        if part_df is not None:
            # need to rename or we have conflict with particle uid field
            to_drop = [col for col in part_df.columns if not col == 'location/micrograph_uid']
            mic_df.drop(columns=to_drop, errors='ignore', inplace=True)
            mic_df = pd.merge(part_df, mic_df, on='location/micrograph_uid', how='outer')

        df = mic_df

    # discard rows with no particles or no micrographs
    if drop_na and df is not None:
        no_parts = pd.isna(df.get('uid', np.array(False)))
        no_mics = pd.isna(df.get('location/micrograph_uid', np.array(False)))
        df = df[~(no_parts | no_mics)]

    return df
