import click


@click.command()
@click.argument('rawtlt_files', nargs=-1, type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-d', '--dose-per-image', type=float, required=True,
              help='electron dose per tilt image (or per frame if inputs are movies)')
@click.option('-p', '--pixel-size', type=float, default=1)
@click.option('-e', '--extension', type=click.Choice(['tif', 'mrc']), default='tif')
@click.option('-f', '--overwrite', is_flag=True)
def cli(rawtlt_files, dose_per_image, pixel_size, extension, overwrite):
    """
    Create dummy mdocs for warp.

    RAWTLT_FILES: simple file with one tilt angle per line. Order should match sorted filenames.
    """
    from mdocfile.mdoc import Mdoc, MdocGlobalData, MdocSectionData
    from pathlib import Path
    from rich.progress import track

    angles = {}
    for ang_file in rawtlt_files:
        with open(ang_file, 'r') as f:
            angles[Path(ang_file).stem] = [float(line) for line in f.readlines() if line]

    datadir = Path(ang_file).parent

    for basename, angles in track(angles.items(), description='Spoofing...'):
        mdoc = Mdoc(
            titles=['[T = Mdoc spoofed by stemia]'],
            global_data=MdocGlobalData(
                ImageFile=basename,
                PixelSpacing=pixel_size
            ),
            section_data=[]
        )
        for img, angle in zip(sorted(datadir.glob(f'{basename}*.{extension}')), angles):

            section = MdocSectionData(
                ZValue=len(mdoc.section_data),
                StagePosition='0 0',
                TiltAngle=angle,
                ExposureDose=dose_per_image,
                SubFramePath=fr'X:\spoof\frames\{img.name}',
            )
            mdoc.section_data.append(section)
        with open(datadir / (basename + '.mdoc'), 'w+' if overwrite else 'w') as f:
            f.write(mdoc.to_string())
