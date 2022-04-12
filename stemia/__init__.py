import click
from pathlib import Path

from .utils.click import add_subcommands

try:
    from ._version import version
except ImportError:
    version = 'unknown'


@click.group(context_settings=dict(help_option_names=['-h', '--help'], show_default=True))
@click.version_option(version=version)
def cli():
    """
    Main entry point for stemia. Several subcommands are available.

    Try `stemia command -h` to get more information.
    """


add_subcommands(cli, Path(__file__).parent, __package__)
