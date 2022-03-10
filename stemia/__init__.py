import click
import pkgutil
import importlib
from pathlib import Path

try:
    from ._version import version
except ImportError:
    version = 'unknown'


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(version=version)
def cli():
    """
    Main entry point for stemia. Several subcommands are available.

    Try `stemia command -h` to get more information.
    """


_submodules = {}
for loader, name, is_pkg in pkgutil.walk_packages([str(Path(__file__).parent)]):
    full_name = __package__ + '.' + name
    module = importlib.import_module(full_name)
    if hasattr(module, 'cli'):
        _submodules[name] = module.cli

for name, command in _submodules.items():
    cli.add_command(command, name=name)
