import click


@click.command()
@click.argument('aln_file', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@click.option('-f', '--overwrite', is_flag=True, help='overwrite existing output')
def cli(aln_file, overwrite):
    """
    Convert AreTomo `aln` file to imod `xf` format.
    """
    from pathlib import Path

    aln_file = Path(aln_file)
    xf_file = aln_file.with_suffix('.xf')
    if xf_file.exists() and not overwrite:
        raise FileExistsError(aln_file)

    import numpy as np
    from io import StringIO

    txt = aln_file.read_text()
    if '# Local Alignment' in txt:
        txt = txt.partition('# Local Alignment')[0]
    data = np.loadtxt(StringIO(txt))
    angles = -np.radians(data[:, 1])
    shifts = data[:, [3, 4]]

    c, s = np.cos(angles), np.sin(angles)
    rot = np.empty((len(angles), 2, 2))
    rot[:, 0, 0] = c
    rot[:, 0, 1] = -s
    rot[:, 1, 0] = s
    rot[:, 1, 1] = c

    shifts_rot = np.einsum('ijk,ik->ij', rot, shifts)

    out = np.concatenate([rot.reshape(-1, 4), -shifts_rot], axis=1)
    np.savetxt(xf_file, out, ['%12.7f'] * 4 + ['%12.3f'] * 2)
