import click


@click.command()
@click.argument('job_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
def cli(job_dir):
    """
    Read cryosparc file(s) and plot interactively any column.

    An interactive ipython shell will be opened with data loaded
    into a pandas dataframe.

    CS_FILE:
        a .cs file followed by any number of passthrough files
    """
    from inspect import cleandoc
    from IPython.terminal.embed import InteractiveShellEmbed

    from .parse import load_job_data
    df = load_job_data(job_dir)

    from .plot import plot_df
    plot_df(df)

    ipython_banner = cleandoc("""
        Imports:
        - numpy as np
        - pandas as pd
        - plotly.express as px
        Variables and functions:
        - parsed data loaded into `df` (pd.DataFrame)
        - call `load_job_data(job_directory)` to read more data
        - call `plot_df(dataframe)` on a dataframe to open the plotting widget
        - call `dataframe.to_csv(...) on a dataframe to save it as csv`
    """)

    sh = InteractiveShellEmbed(banner1=ipython_banner)
    sh.enable_gui('qt')
    sh.push('df')
    sh.run_cell('df')
    sh()
