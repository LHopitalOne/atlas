"""Base class of every sub-command."""

import sys
from abc import ABC, abstractmethod


class Command(ABC):
    name = ''
    help = ''

    @abstractmethod
    def configure(self, parser):
        """Add this command's arguments to its argparse sub-parser."""

    @abstractmethod
    def run(self, args):
        """Do the work. Raise a BridgeError subclass for anything the user can fix."""

    @staticmethod
    def report(message):
        print(message, file=sys.stderr)
