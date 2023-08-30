import click


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
@click.argument('iso_star', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
def cli(warp_dir, iso_star):
    """
    Update an isonet starfile with preprocessing data from warp.
    """
    from pathlib import Path
    warp_dir = Path(warp_dir)
    iso_star = Path(iso_star)

    import starfile
    from xml.etree import ElementTree

    iso = starfile.read(iso_star)
    with click.progressbar(list(iso['rlnMicrographName'].items()), label='Extracting data...') as bar:
        for idx, ts in bar:
            xml = f'{Path(ts).name}.xml'

            et = ElementTree.parse(warp_dir / xml)
            root = et.getroot()
            ctf = root.find('CTF')
            for param in ctf:
                if param.get('Name') == 'Defocus':
                    defocus = float(param.get('Value')) * 10000  # um to A
                    iso.loc[idx, 'rlnDefocus'] = defocus

    starfile.write(iso, iso_star, overwrite=True)
