#!/usr/bin/env python3

import click

from stemia import cli


def get_help(name, cli):
    """Get the help message of a cli recursively."""
    help_msg = []
    if isinstance(cli, click.Group):
        for subname, subcli in cli.commands.items():
            help_msg.extend(get_help(f"{name} {subname}", subcli))
    elif isinstance(cli, click.Command):
        header = f"### {name}\n\n```"
        ctx = click.Context(cli, info_name=name)
        body = cli.get_help(ctx)
        footer = "```"
        help_msg.append("\n".join([header, body, footer]))
    return help_msg


help_msg = get_help("stemia", cli)

print("\n\n".join(help_msg))
