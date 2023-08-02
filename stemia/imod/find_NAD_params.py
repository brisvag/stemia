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
    import re
    from functools import partial

    import mrcfile
    from rich.progress import Progress
    from rich import print
    import sh

    inp = Path(input)
    if std is None:
        with mrcfile.open(input, header_only=True) as mrc:
            std = mrc.header.rms.item()

    ks = [float(k) for k in k_values.split(',')]
    max_it = max(float(it) for it in iterations.split(','))

    it_n = re.compile(r'iteration number:\s+\d+')

    with Progress() as progress:
        def _process_output(task, line):
            if it_n.match(line):
                progress.update(task, advance=1)

        procs = []
        for k_ in ks:
            k = k_ * std
            out = inp.with_stem(inp.stem + f'-{k:.5f}_i').with_suffix('')

            task = progress.add_task(f'Iterating with k={k:.5f} ({k_} * std)...', total=max_it)

            proc = sh.nad_eed_3d(
                '-k', k,
                '-i', iterations,
                '-e', 'mrc',
                str(inp),
                str(out),
                _out=partial(_process_output, task),
                _err=print,
                _bg=True,
            )

            procs.append(proc)

        for proc in procs:
            proc.wait()
