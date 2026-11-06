"""Adapter: SCIP indexes (github.com/sourcegraph/scip) read without a protobuf dependency, the DefinitionOracle
port answered from them, and the indexers that write them."""

from .document import Occurrence, ScipDocument
from .index import ScipIndex
from .indexers import INDEXERS, PythonScipIndexer, RustScipIndexer, ScipIndexer, TypeScriptScipIndexer
from .oracle import ScipOracle
from .symbol import ScipSymbol
from .wire import WireReader

__all__ = [
    'INDEXERS',
    'Occurrence',
    'PythonScipIndexer',
    'RustScipIndexer',
    'ScipDocument',
    'ScipIndex',
    'ScipIndexer',
    'ScipOracle',
    'ScipSymbol',
    'TypeScriptScipIndexer',
    'WireReader',
]
