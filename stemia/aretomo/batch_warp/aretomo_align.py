import click


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
@click.option('-d', '--dry-run', is_flag=True, help='only print some info, without running the commands')
@click.option('-t', '--sample-thickness', type=float, default=1200,
              help='unbinned thickness of the SAMPLE; the reconstruction will be 20% thicker, but this will be used for alignment')
@click.option('-b', '--binning', type=int, help='binning for aretomo reconstruction')
@click.option('-a', '--tilt-axis', type=float, help='starting tilt axis for AreTomo, if any')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite any previous existing run')
@click.option('--fix/--nofix', default=True, help='run ccderaser to fix the stack')
@click.option('--norm/--nonorm', default=False, help='use mrcfile to normalize the images')
@click.option('--align/--noalign', default=True, help='run aretomo to produce an alignment')
@click.option('--startfrom', type=click.Choice(('raw', 'fix', 'norm')), default='raw',
              help='use outputs from a previous run starting from this step')
@click.option('--ccderaser', type=str, default='ccderaser', help='command for ccderaser')
@click.option('--aretomo', type=str, default='AreTomo', help='command for aretomo')
def cli(warp_dir, dry_run, sample_thickness, binning, tilt_axis, overwrite, fix, norm, align, startfrom, ccderaser, aretomo):
    """
    Run aretomo in batch on data preprocessed in warp.

    Needs to be ran after imod stacks were generated. Requires ccderaser and AreTomo.
    Assumes the default Warp directory structure with generated imod stacks. Some warp xml
    files may be updated to disable too dark images.
    """
    from pathlib import Path, PureWindowsPath
    from inspect import cleandoc
    import mdocfile
    from xml.etree import ElementTree

    warp_dir = Path(warp_dir)

    imod_dir = warp_dir / 'imod'
    if not imod_dir.exists():
        raise click.UsageError('warp directory does not have an `imod` subdirectory')

    mdocs = sorted(list(warp_dir.glob('*.mdoc')))
    if not mdocs:
        raise click.UsageError('could not find any mdoc files')

    if not (odd_dir := warp_dir / 'average' / 'odd').exists():
        raise click.UsageError('could not find odd/even averages')
    if not (even_dir := warp_dir / 'average' / 'even').exists():
        raise click.UsageError('could not find odd/even averages')

    tilt_series = {}
    with click.progressbar(mdocs, label='Reading metadata...', item_show_func=lambda x: x.stem if x is not None else None) as bar:
        for mdoc in bar:
            df = mdocfile.read(mdoc)
            ts_name = df.image_file[0].name

            # extract frame paths
            frames = [warp_dir / PureWindowsPath(fr).name for fr in df.sub_frame_path]
            if not all(fr.exists() for fr in frames):
                raise click.UsageError('frame paths in mdocs are wrong or files are missing')

            # extract metadata from warp xmls
            bin = 0
            xml = ElementTree.parse(frames[0].with_suffix('.xml')).getroot()
            for param in xml.find('OptionsCTF'):
                if param.get('Name') == 'BinTimes':
                    bin = float(param.get('Value'))
                elif param.get('Name') == 'Voltage':
                    voltage = int(param.get('Value'))
                elif param.get('Name') == 'Cs':
                    cs = float(param.get('Value'))
            for param in xml.find('CTF'):
                if param.get('Name') == 'Defocus':
                    defocus = float(param.get('Value'))

            tilt_series[ts_name] = {
                'frames': frames,
                'dose': df.exposure_dose[0],
                'px_size': df.pixel_spacing[0] * 2**bin,
                'voltage': voltage,
                'cs': cs,
                'defocus': defocus,
            }

    ts_dirs = sorted([dir for ts_name in tilt_series if (dir := imod_dir / ts_name).is_dir()])

    # if dry_run:
    if True:
        newline = '\n'
        click.secho(cleandoc(f'''
            Warp directory: {warp_dir}
            Tilt series:{''.join(f'{newline}{" " * 16}- {ts.stem}' for ts in ts_dirs)}
            AreTomo options:
                - unbinned thickness: {sample_thickness}
                - tomogram binning: {binning}
        '''))
        click.get_current_context().exit()

    from .funcs import run_fix, run_normalize, run_align

    input_ext = '.st'
    if startfrom == 'fix':
        input_ext = '_fixed.mrc'
        fix = False
    elif startfrom == 'norm':
        input_ext == '_norm.mrc'
        fix = False
        norm = False

    if fix:
        run_fix(ts_list, overwrite, input_ext, ccderaser)
        input_ext = '_fixed.mrc'

    if norm:
        run_normalize(ts_list, overwrite, input_ext)
        input_ext = '_norm.mrc'

    if align:
        run_align(ts_list, overwrite, input_ext, aretomo, tilt_axis)

    run_align(ts_dirs, overwrite, aretomo, tilt_axis)
