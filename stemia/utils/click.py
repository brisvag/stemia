import subprocess
import pkgutil
import importlib
from pathlib import Path

import click


def make_command(file):
    """
    Generate a click command from a simple shell script.
    """
    section = None
    description = []
    args = []
    with open(file, 'r') as f:
        for line in f.readlines()[1:]:  # skip shebang
            line = line.strip('\n')
            if not line:
                continue
            if line.startswith('# DESC'):
                section = description
            elif line.startswith('# ARGS'):
                section = args
            elif line.startswith('# '):
                section.append(line.removeprefix('# '))
            else:
                break

    description.append('')
    params = []
    for arg in reversed(args):
        param, _, help = arg.partition(': ')
        params.append(param)
        if help:
            description.append(f'{param.upper()}: {help}')

    def func(**kwargs):
        subprocess.run(f'{file} {" ".join(kwargs.values())}', check=True, shell=True)

    func.__doc__ = '\n'.join(description)

    for param in params:
        func = click.argument(param)(func)
    func = click.command()(func)

    return func


def add_subcommands(cli, base_dir, base_package):
    """
    Recursively add subcommands to a cli by walking the package tree and looking for
    click functions called `cli`

    cli: root command to attach subcommands to
    base_dir: root directory of the package
    base_package: package name
    """
    source = Path(base_dir)
    has_subcommands = False
    # loop through all the submodules
    for loader, name, is_pkg in pkgutil.walk_packages([str(source)]):
        full_name = base_package + '.' + name
        module = importlib.import_module(full_name)
        # get the cli if it exists
        if hasattr(module, 'cli'):
            cli.add_command(module.cli, name=name)
            has_subcommands = True
        # go deeper if needed
        elif is_pkg:
            def subcli():
                pass
            subcli.__doc__ = module.__doc__
            subcli = click.group()(subcli)
            has_subcommands = add_subcommands(subcli, source / name, full_name)
            if has_subcommands:
                cli.add_command(subcli, name=name)

    # add shell scripts
    for file in source.glob('*.sh'):
        cli.add_command(make_command(file), name=file.stem)
        has_subcommands = True

    return has_subcommands
