"""Values: the strings a Rust expression can hold, as URL templates or as whole channel addresses."""

from .channel import ChannelValues
from .concat import Concatenation
from .fill import FormatFill
from .format import FormatMacro
from .frame import ChannelScope, Frame
from .functions import CrateFunctions
from .pieces import UrlPiece
from .resolver import RustValues
from .structs import CrateStructs
from .types import ValueTypes
from .value import Value, ValueScope

__all__ = [
    'ChannelScope',
    'ChannelValues',
    'Concatenation',
    'CrateFunctions',
    'CrateStructs',
    'FormatFill',
    'FormatMacro',
    'Frame',
    'RustValues',
    'UrlPiece',
    'Value',
    'ValueScope',
    'ValueTypes',
]
