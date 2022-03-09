import click
from pathlib import Path
from inspect import cleandoc


@click.command()
@click.argument('warp_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True), default='.')
@click.option('-d', '--dry-run', is_flag=True, help='only print some info, without running the commands')
@click.option('-t', '--tilt-axis', type=float, help='starting tilt axis for AreTomo, if any')
@click.option('-f', '--overwrite', is_flag=True, help='overwrite any previous existing run')
@click.option('--fix/--nofix', default=True, help='run ccderaser to fix the stack')
@click.option('--norm/--nonorm', default=True, help='use mrcfile to normalize the images')
@click.option('--align/--noalign', default=True, help='run aretomo to produce an alignment')
@click.option('--startfrom', type=click.Choice(('raw', 'fix', 'norm')), default='fix',
              help='use outputs from a previous run starting from this step')
@click.option('--ccderaser', type=str, default='ccderaser', help='command for ccderaser')
@click.option('--aretomo', type=str, default='AreTomo', help='command for aretomo')
def cli(warp_dir, dry_run, ccderaser, aretomo, tilt_axis, overwrite, fix, norm, align, startfrom):
    """
    Run aretomo in batch on data preprocessed in warp.

    Needs to be ran after imod stacks were generated. Requires ccderaser and AreTomo.
    Assumes the default Warp directory structure with generated imod stacks. Some warp xml
    files may be updated to disable too dark images.
    """
    warp_dir = Path(warp_dir)
    imod_dir = warp_dir / 'imod'
    if not imod_dir.exists():
        raise click.UsageError('warp directory does not have an `imod` subdirectory')

    ts_list = sorted([dir for dir in imod_dir.glob('*.mrc') if dir.is_dir()])
    if dry_run:
        newline = '\n'
        click.secho(cleandoc(f'''
            Warp directory:
                - {warp_dir}
            Tilt series found:{''.join(f'{newline}{" " * 16}- {ts.stem}' for ts in ts_list)}
        '''))
        click.get_current_context().exit()

    input_ext = '.mrc.st'
    if startfrom == 'fix':
        input_ext = '_fixed.mrc'
        fix = False
    elif startfrom == 'norm':
        input_ext == '_norm.mrc'
        fix = False
        norm = False

    if fix:
        from .funcs import run_fix
        run_fix(ts_list, overwrite, input_ext, ccderaser)
        input_ext = '_fixed.mrc'

    if norm:
        from .funcs import run_normalize
        run_normalize(ts_list, overwrite, input_ext)
        input_ext = '_norm.mrc'

    if align:
        from .funcs import run_align
        run_align(ts_list, overwrite, input_ext, aretomo, tilt_axis)
