"""The command-line application: registers commands, parses arguments, turns BridgeErrors into exit codes."""

import argparse
import sys

from ..core.errors import BridgeError
from .index import IndexCommand
from .links import LinksCommand
from .map import MapCommand
from .spec import SpecCommand


class App:
    COMMANDS = (MapCommand, SpecCommand, LinksCommand, IndexCommand)

    def __init__(self):
        self._commands = [c() for c in self.COMMANDS]

    def parser(self):
        p = argparse.ArgumentParser(prog='atlas_bridge', description='Graphify graphs and HTTP links on the Atlas map.')
        sub = p.add_subparsers(dest='cmd', required=True)
        for command in self._commands:
            command.configure(sub.add_parser(command.name, help=command.help))
            sub.choices[command.name].set_defaults(command=command)
        return p

    def run(self, argv=None):
        args = self.parser().parse_args(argv)
        try:
            args.command.run(args)
        except BridgeError as e:
            print(f'atlas_bridge {args.cmd}: {e}', file=sys.stderr)
            return e.exit_code
        return 0


def main(argv=None):
    """Run the app; exit with its code when something went wrong."""
    code = App().run(argv)
    if code:
        sys.exit(code)
