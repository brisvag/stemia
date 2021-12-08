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
    from magicgui import magicgui
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
                el = df[col].iloc[0]
                if isinstance(el, np.ndarray):
                    split_col = pd.DataFrame(
                        df[col].tolist(),
                        columns=[f'{col}_{i}' for i in range(len(el))]
                    )
                    cols.append(split_col)
                else:
                    cols.append(df[col])
            df = pd.concat(cols, axis=1)
            dfs.append(df)
        return reduce(lambda left, right: pd.merge(left, right, on='uid'), dfs)

    df = read_cs(*cs_file)

    columns = ['index'] + df.columns.tolist()
    modes = [('scatter', px.scatter), ('histogram', px.histogram), ('line', px.line)]

    @magicgui(
        call_button='Plot',
        x={'choices': columns},
        y={'choices': columns},
        mode={'choices': modes}
    )
    def make_plot(x, y, mode):
        kwargs = dict(data_frame=df, x=x, y=y)
        mode(**kwargs).show()

    make_plot.show()

    banner = f"""
- numpy imported as np
- pandas imported as pd
- dataframe loaded as df
- call read_cs([file1, file2]) to read more data

{df}
"""

    sh = InteractiveShellEmbed(banner1=banner)
    sh.enable_gui('qt')
    sh()
