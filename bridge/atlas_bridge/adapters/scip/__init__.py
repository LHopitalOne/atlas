"""Adapter: SCIP indexes (github.com/sourcegraph/scip) read without a protobuf dependency, the DefinitionOracle
and CallGraph ports answered from them, and the indexers that write them (optionally in a Docker sandbox)."""

from .callgraph import ScipCallGraph
from .dependencies import PythonDependencies
from .document import Occurrence, ScipDocument
from .index import ScipIndex
from .indexers import INDEXERS, PythonScipIndexer, RustScipIndexer, ScipIndexer, TypeScriptScipIndexer
from .oracle import ScipOracle
from .sandbox import DockerImage, SandboxedPythonIndexer
from .symbol import ScipSymbol
from .wire import WireReader

__all__ = [
    'INDEXERS',
    'DockerImage',
    'Occurrence',
    'PythonDependencies',
    'PythonScipIndexer',
    'RustScipIndexer',
    'SandboxedPythonIndexer',
    'ScipCallGraph',
    'ScipDocument',
    'ScipIndex',
    'ScipIndexer',
    'ScipOracle',
    'ScipSymbol',
    'TypeScriptScipIndexer',
    'WireReader',
]
