import click


@click.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.argument('particles', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
def main(particles):
    import numpy as np
    import pandas as pd
    import plotly.express as px
    from magicgui import magicgui
    from IPython.terminal.embed import InteractiveShellEmbed

    click.secho(f'Reading "{particles}"...')
    data = np.load(particles)
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

    banner = f'Columns: \n{list(df.columns)}'

    sh = InteractiveShellEmbed(banner1=banner)
    sh.enable_gui('qt')
    sh()
