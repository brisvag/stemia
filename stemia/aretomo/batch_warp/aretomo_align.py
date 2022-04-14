import click


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
@click.option('-m', '--mdoc-dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
@click.option('-d', '--dry-run', is_flag=True, help='only print some info, without running the commands')
@click.option('-o', '--only', type=str, multiple=True,
              help='quickly reconstruct just this tomogram with a simple setup. Useful for testing and to estimate sample thickness')
@click.option('-t', '--thickness', type=int, default=1200,
              help='unbinned thickness of the SAMPLE (ice or lamella); the reconstruction will be 20% thicker, but this will be used for alignment')
@click.option('-b', '--binning', type=int, default=4, help='binning for aretomo reconstruction')
@click.option('-a', '--tilt-axis', type=float, help='starting tilt axis for AreTomo, if any')
@click.option('-p', '--patches', type=int, default=4, help='number of patches for local alignment in aretomo (NxN)')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite any previous existing run')
@click.option('--fix/--nofix', default=True, help='run ccderaser to fix the stack')
@click.option('--norm/--nonorm', default=True, help='use mrcfile to normalize the images')
@click.option('--align/--noalign', default=True, help='run aretomo to produce an alignment')
@click.option('--startfrom', type=click.Choice(('auto', 'fix', 'norm', 'ali')), default='auto',
              help='use outputs from a previous run, starting processing at this step')
@click.option('--ccderaser', type=str, default='ccderaser', help='command for ccderaser')
@click.option('--aretomo', type=str, default='AreTomo', help='command for aretomo')
def cli(warp_dir, mdoc_dir, dry_run, only, thickness, binning, tilt_axis, patches, overwrite, fix, norm, align, startfrom, ccderaser, aretomo):
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

    if mdoc_dir is None:
        mdoc_dir = warp_dir
    if only is not None:
        mdocs = [Path(mdoc_dir) / (ts_name + '.mdoc') for ts_name in only]
    else:
        mdocs = sorted(list(Path(mdoc_dir).glob('*.mdoc')))
    if not mdocs:
        raise click.UsageError('could not find any mdoc files')

    if not (odd_dir := warp_dir / 'average' / 'odd').exists():
        raise click.UsageError('could not find odd/even averages')
    if not (even_dir := warp_dir / 'average' / 'even').exists():
        raise click.UsageError('could not find odd/even averages')

    recon_thickness = int(thickness * 1.3)

    tilt_series = {}
    tilt_series_unprocessed = {}
    with click.progressbar(mdocs, label='Reading metadata...', item_show_func=lambda x: x.stem if x is not None else None) as bar:
        for mdoc in bar:
            df = mdocfile.read(mdoc)
            ts_name = df.image_file[0].name
            ts_dir = imod_dir / ts_name

            # skip if not preprocessed in warp
            if not ts_dir.is_dir():
                tilt_series_unprocessed.append(ts_name)
                continue

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
                    kv = int(param.get('Value'))
                elif param.get('Name') == 'Cs':
                    cs = float(param.get('Value'))
            for param in xml.find('CTF'):
                if param.get('Name') == 'Defocus':
                    defocus = float(param.get('Value'))

            tilt_series[ts_name] = {
                'dir': ts_dir,
                'frames': frames,
                'aretomo_kwargs': {
                    'dose': df.exposure_dose[0],
                    'px_size': df.pixel_spacing[0] * 2**bin,
                    'cs': cs,
                    'kv': kv,
                    'defocus': defocus,
                },
            }

    newline = '\n'
    click.secho(cleandoc(f'''
        Warp directory: {warp_dir}
        Mdoc directory: {mdoc_dir}
        Tilt series:{''.join(f'{newline}{" " * 12}- {ts.stem}' for ts in ts_dirs)}
        AreTomo options:
            - alignment thickness: {thickness}
            - reconstruction thickness: {recon_thickness}
            - tomogram binning: {binning}
    '''))
    if dry_run:
        click.get_current_context().exit()

    from .funcs import run_fix, run_normalize, run_align, outputs_exist

    ts_dirs = list(ts['dir'] for ts in tilt_series.values())

    if startfrom == 'auto':
        if outputs_exist(ts_dirs, '.fixed'):
            startfrom = 'norm'
        if outputs_exist(ts_dirs, '.norm'):
            startfrom = 'ali'
        if outputs_exist(ts_dirs, '.aligned'):
            raise click.UsageError('all outputs appear to exist. Do you need to change some parameter?')

    input_ext = '.st'
    if startfrom == 'norm':
        input_ext = '.fixed'
        fix = False
    elif startfrom == 'ali':
        input_ext = '.norm'
        fix = False
        norm = False

    if fix:
        run_fix(ts_dirs, overwrite, input_ext, cmd=ccderaser)
        input_ext = '.fixed'

    if norm:
        run_normalize(ts_dirs, overwrite, input_ext)
        input_ext = '.norm'

    if align:
        run_align(
            tilt_series,
            overwrite,
            input_ext,
            cmd=aretomo,
            tilt_axis=tilt_axis,
            patches=patches,
            thickness_align=thickness,
            thickness_recon=recon_thickness,
            binning=binning),
        input_ext = '.aligned'
