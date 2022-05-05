import click


@click.command()
@click.argument('cs_file', type=click.Path(exists=True, dir_okay=False, resolve_path=True), nargs=-1)
def cli(cs_file):
    """
    Read cryosparc file(s) and plot interactively any column.

    An interactive ipython shell will be opened with data loaded
    into a pandas dataframe.

    CS_FILE:
        a .cs file followed by any number of passthrough files
    """
    import sys
    if not cs_file:
        sys.exit()

    from functools import reduce
    from inspect import cleandoc
    import numpy as np
    import pandas as pd
    import plotly.express as px
    from magicgui import magic_factory
    from IPython.terminal.embed import InteractiveShellEmbed

    def read_cs(*args):
        """
        Read a cryosparc file (+ any number of passthrough files) into a pandas dataframe

        args: list of strings/pathlike

        Returns a merged dataframe.
        """
        dfs = []
        for path in args:
            click.secho(f'Reading "{path}"...')
            data = np.load(path)

            click.secho('Converting to pandas dataframe...')
            df = pd.DataFrame(data.tolist(), columns=data.dtype.names)

            click.secho('Flattening nested columns...')
            cols = []
            for col in df.columns:
                # check first element for the rest
                el = df[col].iloc[0]
                if isinstance(el, np.ndarray):
                    # split columns and add index at the end (e.g: pose_0, pose_1, pose_2)
                    split_col = pd.DataFrame(
                        df[col].tolist(),
                        columns=[f'{col}_{i}' for i in range(len(el))]
                    )
                    cols.append(split_col)
                else:
                    cols.append(df[col])
            # stitch them back together
            df = pd.concat(cols, axis=1)
            dfs.append(df)
        # merge everything based on unique id
        return reduce(lambda left, right: pd.merge(left, right, on='uid'), dfs)

    modes = [('scatter', px.scatter), ('histogram', px.histogram), ('line', px.line)]
    histfuncs = ['count', 'sum', 'avg', 'min', 'max']

    @magic_factory(
        main_window=True,
        call_button='Plot',
        x={'widget_type': 'ComboBox'},
        y={'widget_type': 'ComboBox'},
        color={'widget_type': 'ComboBox'},
        mode={'choices': modes},
        histfunc={'choices': histfuncs},
    )
    def plot_widget(dataframe, x, y, color, mode, histfunc):
        if x == 'index':
            x = dataframe.index
        if y == 'index':
            y = dataframe.index
        kwargs = dict(data_frame=dataframe, x=x, y=y, color=color)
        if mode is px.histogram:
            kwargs['histfunc'] = histfunc
        mode(**kwargs).show()

    def plot_df(dataframe):
        pw = plot_widget()
        # set new dataframe as source and regenerate choices?
        pw.dataframe.value = dataframe
        columns = ['index'] + df.columns.tolist()
        pw.x.choices = columns
        pw.y.choices = [None] + columns
        pw.color.choices = [None] + columns
        pw.show()

    df = read_cs(*cs_file)
    plot_df(df)

    ipython_banner = cleandoc("""
        Imports:
        - numpy as np
        - pandas as pd
        - plotly.express as px
        Variables and functions:
        - parsed data loaded into `df` (pd.DataFrame)
        - call `read_cs([file1, file2])` to read more data
        - call `plot_df(dataframe)` on a dataframe to open the plotting widget
        - call `dataframe.to_csv(...) on a dataframe to save it as csv`
    """)

    sh = InteractiveShellEmbed(banner1=ipython_banner)
    sh.enable_gui('qt')
    sh.push('df')
    sh.run_cell('df')
    sh()
