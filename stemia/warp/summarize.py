import click


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True), default='.')
def cli(warp_dir):
    """
    Summarize the state of a Warp project.

    Reports for each tilt series:
    - discarded: number of discarded tilts
    - total: total number oftilts in raw data
    - stacked: number of image slices in imod output directory
    - mismatch: whether stacked != (total - discarded)
    - resolution: estimated resolution if processed
    """
    from pathlib import Path
    import re
    from xml.etree import ElementTree
    from tabulate import tabulate
    import mrcfile

    columns = ['discarded', 'total', 'stacked', 'mismatch', 'resolution']

    warp_dir = Path(warp_dir)
    tilts = warp_dir.glob('*_*_*.xml')
    ts_data = {}
    for tilt in tilts:
        name = re.search(r'(.+)_\d+_[\d.-]+', tilt.stem).group(1)
        if name not in ts_data:
            ts_data[name] = [0, 0, 0, None, None]
        xml = ElementTree.parse(tilt).getroot()
        ts_data[name][0] += xml.attrib['UnselectManual'] == 'True'
        ts_data[name][1] += 1  # total

    for st in (warp_dir / 'imod').iterdir():
        try:
            data = ts_data[st.stem]
            with mrcfile.open((st / (st.name + '.st')), header_only=True) as mrc:
                data[2] = mrc.header.nz  # stacked
                if data[2] != data[1] - data[0]:
                    data[3] = 'X'  # mismatch
        except (FileNotFoundError, KeyError):
            pass

    tomos = warp_dir.glob('*.mrc.xml')
    for tomo in tomos:
        name = re.search(r'(.+).mrc', tomo.stem).group(1)
        xml = ElementTree.parse(tomo).getroot()
        ts_data[name][4] = float(xml.attrib['CTFResolutionEstimate'])

    table = {k: list() for k in ['tilt_series', *columns]}
    for name, data in ts_data.items():
        table['tilt_series'].append(name)
        for k, v in zip(columns, data):
            table[k].append(v)

    print(tabulate(table, headers='keys'))
