"""The `atlas` command: `atlas ./repo [./repo2 ...]` is `atlas-bridge map ./repo [./repo2 ...]`."""

import argparse
import sys
from importlib import metadata

from ..core.errors import BridgeError
from .map import MapCommand


class AtlasApp:
    PROG = 'atlas'
    INTERRUPTED = 130

    def __init__(self):
        self._command = MapCommand()

    def parser(self):
        p = argparse.ArgumentParser(
            prog=self.PROG,
            description='Map repositories with Graphify, find the HTTP links between them, and open the zoomable map.',
        )
        p.add_argument('--version', action='version', version=f'%(prog)s {self.version()}')
        self._command.configure(p)
        return p

    def run(self, argv=None):
        args = self.parser().parse_args(argv)
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
