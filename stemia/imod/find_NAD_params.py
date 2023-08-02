import click


@click.command()
@click.argument('input', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-k', '--k-values', type=str, default="0.2,0.4,0.8,1.2,3,5")
@click.option('-i', '--iterations', type=str, default="2,5,8,10,15,20")
@click.option('-s', '--std', type=str)
def cli(input, k_values, iterations, std):
    """
    Test a range of k and iteration values for nad_eed_3d
    """
    from pathlib import Path
    import mrcfile
    from io import StringIO
    from rich.progress import track
    import sh

    inp = Path(input)
    if std is None:
        with mrcfile.open(input, header_only=True) as mrc:
            std = mrc.header.rms.item()

    stdout = StringIO()

    ks = [float(k) for k in k_values.split(',')]
    for k in track(ks, description='Denoising...'):
        k = k * std
        out = inp.with_stem(inp.stem + f'-{k:.5f}_i').with_suffix('')

        try:
            sh.nad_eed_3d(
                '-k', k,
                '-i', iterations,
                '-e', 'mrc',
                str(inp),
                str(out),
                _out=stdout,
                _err=stdout,
            )
        except:
            print(stdout.getvalue())
