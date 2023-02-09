import click


@click.command()
@click.argument('data_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
def cli(data_dir):
    """
    Fix mdoc files to point to the right data.
    """
    from mdocfile.mdoc import Mdoc
    from pathlib import Path
    from rich.progress import track
    from rich import print

    data_dir = Path(data_dir)
    mdocs = [f for f in data_dir.glob('*.mdoc') if not f.stem.endswith('_fixed')]
    failed = {}
    with track(mdocs, description='Fixing...') as bar:
        for md_file in bar:
            mdoc = Mdoc.from_file(md_file)
            basename = mdoc.global_data.ImageFile.stem
            cleaned_sections = []
            for section in mdoc.section_data:
                # find correct file based on basename, zvalue and tilt angle
                glob = f'{basename}_{section.ZValue + 1:03}_{round(section.TiltAngle):.2f}_*.mrc'
                try:
                    newpath = next(data_dir.glob(glob))
                except StopIteration:
                    failed.setdefault(mdoc, list).append(glob)
                    continue
                # replace path with the correct file (only name matters)
                section.SubFramePath = fr'X:\spoof\frames\{newpath.name}'
                cleaned_sections.append(section)

            mdoc.section_data = cleaned_sections

        if failed:
            print('No files matching the followings sections:')
            for k, v in failed:
                print(k.name, ':')
                print('\n- '.join(v))

            with open(md_file.parent / (md_file.stem + '_fixed.mdoc'), 'w+') as f:
                f.write(mdoc.to_string())
