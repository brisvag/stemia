import click

from ..utils.io_ import xml2dict


@click.command()
@click.argument('xml_file', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
def cli(xml_file):
    """
    Parse a warp xml file and print its content.
    """
    import pprint
    data = xml2dict(xml_file)
    pprint.pprint(data)
