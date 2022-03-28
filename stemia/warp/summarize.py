import click


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True), default='.')
def cli(warp_dir):
    """
    Summarize the state of a Warp project.
    """
    from pathlib import Path
    import re
    from collections import defaultdict
    from xml.etree import ElementTree
    from rich import print

    warp_dir = Path(warp_dir)

    tilts = warp_dir.glob('*_*_*.xml')
    ts_data = defaultdict(dict)
    for tilt in tilts:
        name = re.search(r'(.+)_\d+_[\d.-]+', tilt.stem).group(1)
        if name not in ts_data:
            ts_data[name] = {
                'discarded': 0,
                'total': 0,
                'res_estimate': None,
            }
        xml = ElementTree.parse(tilt).getroot()
        ts_data[name]['discarded'] += xml.attrib['UnselectManual'] == 'True'
        ts_data[name]['total'] += 1

    tomos = warp_dir.glob('*.mrc.xml')
    for tomo in tomos:
        name = re.search(r'(.+).mrc', tomo.stem).group(1)
        xml = ElementTree.parse(tomo).getroot()
        ts_data[name]['res_estimate'] = float(xml.attrib['CTFResolutionEstimate'])

    for ts, dct in sorted(ts_data.items()):
        print(ts, ' '.join(str(v) for v in dct.values()))
