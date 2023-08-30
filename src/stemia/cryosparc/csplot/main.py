import click


@click.command()
@click.argument('job_dir', type=click.Path(exists=True, dir_okay=True, resolve_path=True))
@click.option('--drop-na', is_flag=True, help='drop rows that contain NaN values (e.g: micrographs with no particles)')
@click.option('--no-particles', is_flag=True, help='do not read particles data')
@click.option('--no-micrographs', is_flag=True, help='do not read micrographs data')
def cli(job_dir, drop_na, no_particles, no_micrographs):
    """
    Read a cryosparc job directory and plot interactively any column.

    All the related data from parent jobs will also be loaded.
    An interactive ipython shell will be opened with data loaded
    into a pandas dataframe.

    JOB_DIR:
        a cryosparc job directory.
    """
    from inspect import cleandoc
    from IPython.terminal.embed import InteractiveShellEmbed

    from .parse import load_job_data
    df = load_job_data(job_dir, drop_na=drop_na, micrographs=not no_micrographs, particles=not no_particles)

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

    import pandas as pd, numpy as np, plotly.express as px

    sh = InteractiveShellEmbed(banner1=ipython_banner)
    sh.enable_gui('qt')
    sh.push('df')
    sh.run_cell('df')
    sh()
