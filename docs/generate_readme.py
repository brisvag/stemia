#!/usr/bin/env python3

from stemia import cli
import click


def get_help(name, cli):
    help = []
    if isinstance(cli, click.Group):
        for subname, subcli in cli.commands.items():
            help.extend(get_help(f'{name} {subname}', subcli))
    elif isinstance(cli, click.Command):
        header = f'### {name}\n\n```'
        ctx = click.Context(cli, info_name=name)
        body = cli.get_help(ctx)
        footer = '```'
        help.append('\n'.join([header, body, footer]))
    return help


help = get_help('stemia', cli)

print('\n\n'.join(help))
