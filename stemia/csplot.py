import click


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('cs_file', type=click.Path(exists=True, dir_okay=False, resolve_path=True), nargs=-1)
def main(cs_file):
    """
    read a cryosparc file (plus any number of passthrough files) into a pandas dataframe
    and provide a simple interface for plotting columns.
    Provided files must be compatible (have the same uid column!)
    """
    from functools import reduce
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

    df = read_cs(*cs_file)

    columns = ['index'] + df.columns.tolist()
    modes = [('scatter', px.scatter), ('histogram', px.histogram), ('line', px.line)]
    histfuncs = ['count', 'sum', 'avg', 'min', 'max']

    @magic_factory(
        main_window=True,
        call_button='Plot',
        x={'choices': columns},
        y={'choices': [None] + columns},
        color={'choices': [None] + columns},
        histfunc={'choices': histfuncs},
        mode={'choices': modes},
    )
    def plot_widget(dataframe, x, y, color, histfunc, mode):
        kwargs = dict(data_frame=df, x=x, y=y, color=color)
        if mode is px.histogram:
            kwargs['histfunc'] = histfunc
        mode(**kwargs).show()

    def plot_df(dataframe):
        pw = plot_widget()
        pw.dataframe.value = dataframe
        pw.show()

    plot_df(df)

    banner = f"""
Imports:
- numpy as np
- pandas as pd
- plotly.express as px
Variables and functions:
- parsed data loaded into `df` (pd.DataFrame)
- call `read_cs([file1, file2])` to read more data
- call `plot_df(dataframe)` on a dataframe to open the plotting widget

{df}
"""

    sh = InteractiveShellEmbed(banner1=banner)
    sh.enable_gui('qt')
    sh()
