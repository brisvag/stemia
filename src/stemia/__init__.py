"""Stemia entry point."""

from pathlib import Path

import click

from .utils.click import add_subcommands, print_command_tree

try:
    from ._version import version
except ImportError:
    version = "unknown"


def _print_tree(ctx, param, value):
    if value:
        print_command_tree(cli)
        ctx.exit()


@click.group(
    name="stemia",
    context_settings={"help_option_names": ["-h", "--help"], "show_default": True},
)
@click.version_option(version=version)
@click.option(
    "-l",
    "--list",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    callback=_print_tree,
    help="print all the available commands",
)
def cli():
    """
    Main entry point for stemia. Several subcommands are available.

    Try `stemia command -h` to get more information.
    """


add_subcommands(cli, Path(__file__).parent, __package__)
