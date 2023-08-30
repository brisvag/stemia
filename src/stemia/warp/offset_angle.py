import click


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True), default='.')
def cli(warp_dir, offset):
    """
    Offset tilt angles in warp xml files.
    """
    import mdocfile

    from xml.etree import ElementTree
    from pathlib import Path
    import shutil

    warp_dir = Path(warp_dir)
    mdocs = list(warp_dir.glob('*.mdoc'))
    with click.progressbar(mdocs, label='Fixing...') as bar:
        for md_file in bar:
            df = mdocfile.read(md_file)
            zero_angle = df.tilt_angle[df.dose_rate.idxmax()]
            print(mdoc)

    bak = list(warp_dir.glob('*.mrc.xml.bak'))
    xmls = list(warp_dir.glob('*.mrc.xml'))
    if bak:
        if len(bak) != len(xmls):
            raise RuntimeError(f'Something went wrong: found {len(bak)} `.bak` files and {len(xmls)} `.xml` files.')
    else:
        with click.progressbar(xmls, label='Backing up...') as bar:
            for xml in bar:
                shutil.copy(xml, f'{xml}.bak')
        bak = list(warp_dir.glob('*.mrc.xml.bak'))

    with click.progressbar(bak, label='Editing xml files...') as bar:
        for xml in bar:
            et = ElementTree.parse(xml)
            angles_node = et.getroot().find('Angles')
            offset_angles = [int(ang) + offset for ang in angles_node.text.split()]
            new_angles_text = '\n'.join(str(ang) for ang in offset_angles)
            angles_node.text = new_angles_text
            # readd the windows carriage return because they get lost in parsing...
            # not 100% right, but makes diffing easier
            for node in et.getroot().iter():
                if isinstance(node.tail, str) and '\r' not in node.tail:
                    node.tail = node.tail.replace('\n', '\r\n')
            et.write(xml.with_suffix(''), encoding='utf-16', xml_declaration=True)
