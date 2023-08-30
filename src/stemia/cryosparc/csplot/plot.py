import plotly.express as px
from magicgui import magic_factory

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
    columns = ['index'] + dataframe.columns.tolist()
    pw.x.choices = columns
    pw.y.choices = [None] + columns
    pw.color.choices = [None] + columns
    pw.show()
