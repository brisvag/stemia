import click


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
@click.option('-m', '--mdoc-dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
@click.option('-d', '--dry-run', is_flag=True, help='only print some info, without running the commands.')
@click.option('-v', '--verbose', is_flag=True, help='print individual commands')
@click.option('-o', '--only', type=str, multiple=True,
              help='quickly reconstruct just this tomogram with a simple setup. Useful for testing and to estimate sample thickness')
@click.option('-t', '--thickness', type=int, default=1200,
              help='unbinned thickness of the SAMPLE (ice or lamella); the reconstruction will be 20% thicker, but this will be used for alignment')
@click.option('-b', '--binning', type=int, default=4, help='binning for aretomo reconstruction (relative to warp binning)')
@click.option('-a', '--tilt-axis', type=float, help='starting tilt axis for AreTomo, if any')
@click.option('-p', '--patches', type=int, default=4, help='number of patches for local alignment in aretomo (NxN)')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite any previous existing run')
@click.option('--fix/--no-fix', default=True, help='run ccderaser to fix the stack')
@click.option('--align/--no-align', default=True, help='run aretomo to produce an alignment')
@click.option('--aretomo-denoise/--no-aretomo-denoise', default=True, help='use even/odd frames to generate denoised aretomo reconstructions')
@click.option('--startfrom', type=click.Choice(('auto', 'fix', 'ali')), default='auto',
              help='use outputs from a previous run, starting processing at this step')
@click.option('--ccderaser', type=str, default='ccderaser', help='command for ccderaser')
@click.option('--aretomo', type=str, default='AreTomo', help='command for aretomo')
def cli(warp_dir, mdoc_dir, dry_run, verbose, only, thickness, binning, tilt_axis, patches, overwrite, fix, align, aretomo_denoise, startfrom, ccderaser, aretomo):
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
    from rich.progress import track
    from rich.panel import Panel
    from rich import print

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

    odd_dir = warp_dir / 'average' / 'odd'
    even_dir = warp_dir / 'average' / 'even'

    tilt_series = {}
    tilt_series_unprocessed = {}
    for mdoc in track(mdocs, 'Reading mdocs...'):
        df = mdocfile.read(mdoc)
        ts_name = df.image_file[0].name
        stack = imod_dir / ts_name / (ts_name + '.st')

        # skip if not preprocessed in warp
        if not stack.exists():
            tilt_series_unprocessed.append(ts_name)
            continue

        # extract even/odd paths
        tilts = [warp_dir / PureWindowsPath(tilt).name for tilt in df.sub_frame_path]
        odd = []
        even = []
        for tilt in tilts:
            xml = ElementTree.parse(tilt.with_suffix('.xml')).getroot()
            if xml.attrib['UnselectManual'] == 'True':
                continue

            odd.append(odd_dir / (tilt.stem + '.mrc'))
            even.append(even_dir / (tilt.stem + '.mrc'))

        if aretomo_denoise:
            for img in odd + even:
                if not img.exists():
                    raise FileNotFoundError(img)

        # extract metadata from warp xmls (we assume the last xml has the same data as the others)
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
            'stack': stack,
            'odd': odd,
            'even': even,
            'aretomo_kwargs': {
                'dose': df.exposure_dose[0],
                'px_size': df.pixel_spacing[0] * 2**bin,
                'cs': cs,
                'kv': kv,
                'defocus': defocus,
            },
        }

    aretomo_kwargs = dict(
        cmd=aretomo,
        tilt_axis=tilt_axis,
        patches=patches,
        thickness_align=thickness,
        thickness_recon=int(thickness * 1.3),
        binning=binning,
    )

    meta_kwargs = dict(
        overwrite=overwrite,
        dry_run=dry_run,
        verbose=verbose,
    )

    in_ext = ''
    if startfrom == 'ali':
        in_ext = '_fix'
        fix = False

    newline = '\n'
    print(Panel(cleandoc(f'''
        [bold]Warp directory[/bold]: {warp_dir}
        [bold]Mdoc directory[/bold]: {mdoc_dir}
        [bold]Tilt series - NOT READY[/bold]: {''.join(f'{newline}{" " * 12}- {ts}' for ts in tilt_series_unprocessed)}
        [bold]Tilt series - READY[/bold]: {''.join(f'{newline}{" " * 12}- {ts}' for ts in tilt_series)}
        [bold]Starting from[/bold]: {startfrom}
        [bold]Run options[/bold]: {''.join(f'{newline}{" " * 12}- {k}: {v}' for k, v in meta_kwargs.items())}
        [bold]AreTomo options[/bold]: {''.join(f'{newline}{" " * 12}- {k}: {v}' for k, v in aretomo_kwargs.items())}
    ''')))

    from .funcs import fix_batch, aretomo_batch, prepare_half_stacks

    if fix:
        if verbose:
            print('\n[green]Fixing with ccderaser...')
        fix_batch(tilt_series, cmd=ccderaser, **meta_kwargs)
        in_ext = '_fix'

    if align:
        if verbose:
            print('\n[green]Aligning and reconstructing with AreTomo...')
        aretomo_batch(
            tilt_series,
            in_ext=in_ext,
            **aretomo_kwargs,
            **meta_kwargs,
        )
        in_ext = '_aligned'

    if aretomo_denoise:
        if verbose:
            print('\n[green]Preparing half stacks for denoising...')
        prepare_half_stacks(tilt_series)
        if verbose:
            print('\n[green]Reconstructing half tomograms for deonoising...')
        aretomo_batch(
            tilt_series,
            input_ext='_odd',
            output_ext='_odd',
            from_aln=True,
            **aretomo_kwargs,
            **meta_kwargs,
        )
