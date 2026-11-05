"""The Python workspace: modules, names, locals, class attributes and callers, indexed once per repository."""

from .callers import CallerIndex
from .locals import ClassAttributes, LocalAssignment, LocalIndex
from .modules import AbsoluteModule, ModuleIndex, ModuleRef, RelativeModule
from .names import NameLookup, Symbol
from .table import Import, ModuleTable
from .workspace import PythonWorkspace

__all__ = [
    'AbsoluteModule',
    'CallerIndex',
    'ClassAttributes',
    'Import',
    'LocalAssignment',
    'LocalIndex',
    'ModuleIndex',
    'ModuleRef',
    'ModuleTable',
    'NameLookup',
    'PythonWorkspace',
    'RelativeModule',
    'Symbol',
]
