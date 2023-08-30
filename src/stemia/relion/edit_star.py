import click


@click.command()
@click.argument(
    "star_files",
    nargs=-1,
    type=click.Path(exists=True, dir_okay=False, resolve_path=True),
)
@click.option(
    "-s",
    "--suffix-output",
    type=str,
    default="_modified",
    help="suffix added to the output files before extension",
)
@click.option("-c", "--column", type=str, multiple=True, help="column(s) to modify")
@click.option(
    "-i", "--regex-in", type=str, multiple=True, help="regex sed-like search pattern(s)"
)
@click.option(
    "-o",
    "--regex-out",
    type=str,
    multiple=True,
    help="regex sed-like substitution to apply to the column(s)",
)
@click.option("-f", "--overwrite", is_flag=True, help="overwrite output if exists")
def cli(star_files, suffix_output, column, regex_in, regex_out, overwrite):
    """
    Simple search-replace utility for star files.

    Full regex functionality works (e.g: reusing groups in output)
    """
    from pathlib import Path

    import starfile
    from rich.progress import track

    outputs = [Path(f).with_stem(Path(f).stem + suffix_output) for f in star_files]
    for f in outputs:
        if f.is_file() and not overwrite:
            raise click.UsageError(f'{f} exists but "-f" flag was not passed')

    if len(column) != len(regex_in) or len(regex_in) != len(regex_out):
        raise click.UsageError(
            "must pas column and regexes the same number of times; "
            f"got {len(column)}, {len(regex_in)} and {len(regex_out)}."
        )

    for star_file, output in zip(
        track(star_files, description="Processing..."), outputs
    ):
        data = starfile.read(star_file, always_dict=True)

        for _k, df in data.items():
            for col, reg_in, reg_out in zip(column, regex_in, regex_out):
                dt = df[col].dtype
                col_str = df[col].astype(str)
                modified = col_str.str.replace(reg_in, reg_out, regex=True)
                df[col] = modified.astype(dt)

        starfile.write(data, output, overwrite=overwrite, sep=" ")
