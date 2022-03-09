#!/usr/bin/env python3

from stemia import cli
import click

readme = []

for name, cmd in cli.commands.items():
    header = f'### {name}\n\n```'
    ctx = click.Context(cmd, info_name='stemia ' + name)
    body = cmd.get_help(ctx)
    footer = '```'
    readme.append('\n'.join([header, body, footer]))

print('\n\n'.join(readme))
