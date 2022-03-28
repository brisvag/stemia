import click


@click.command()
@click.argument('data_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
def cli(data_dir):
    """
    Fix mdoc files to point to the right data.
    """
    from mdocfile.mdoc import Mdoc
    from pathlib import Path

    data_dir = Path(data_dir)
    mdocs = list(data_dir.glob('*.mdoc'))
    with click.progressbar(mdocs, label='Fixing...') as bar:
        for md_file in bar:
            mdoc = Mdoc.from_file(md_file)
            basename = mdoc.global_data.ImageFile.stem
            for section in mdoc.section_data:
                # find correct file based on basename, zvalue and tilt angle
                glob = f'{basename}_{section.ZValue + 1:03}_{round(section.TiltAngle):.2f}_*.mrc'
                newpath = list(data_dir.glob(glob))[0]
                # replace path with the correct file (only name matters)
                section.SubFramePath = fr'X:\spoof\frames\{newpath.name}'

            with open(md_file.parent / (md_file.stem + '_fixed.mdoc'), 'w+') as f:
                f.write(mdoc.to_string())
