"""The `atlas` command: `atlas ./repo [./repo2 ...]` is `atlas-bridge map ./repo [./repo2 ...]`, and
`atlas serve [atlas-out]` shows a written map from a local server (`atlas-bridge serve`)."""

import argparse
import sys
from importlib import metadata

from ..core.errors import BridgeError
from .map import MapCommand
from .serve import ServeCommand


class AtlasApp:
    PROG = 'atlas'
    INTERRUPTED = 130

    SERVE = 'serve'

    def __init__(self):
        self._command = MapCommand()

    def parser(self, serve=False):
        if serve:  # `atlas serve ...`: a folder that is literally named serve can be passed as ./serve
            self._command = ServeCommand()
            p = argparse.ArgumentParser(prog=f'{self.PROG} {self.SERVE}', description=ServeCommand.help)
            self._command.configure(p)
            return p
        p = argparse.ArgumentParser(
            prog=self.PROG,
            description='Map repositories with Graphify, find the HTTP links between them, and open the zoomable map.',
        )
        p.add_argument('--version', action='version', version=f'%(prog)s {self.version()}')
        self._command.configure(p)
        return p

    def run(self, argv=None):
        argv = list(sys.argv[1:] if argv is None else argv)
        serve = bool(argv) and argv[0] == self.SERVE
        args = self.parser(serve).parse_args(argv[1:] if serve else argv)
        try:
            self._command.run(args)
        except BridgeError as e:
            print(f'{self.PROG}: {e}', file=sys.stderr)
            return e.exit_code
        except KeyboardInterrupt:
            print(f'{self.PROG}: stopped', file=sys.stderr)
            return self.INTERRUPTED
        return 0

    @staticmethod
    def version():
        try:
            return metadata.version('atlas-bridge')
        except metadata.PackageNotFoundError:
            return 'unknown'


def atlas_main(argv=None):
    code = AtlasApp().run(argv)
    if code:
        sys.exit(code)
