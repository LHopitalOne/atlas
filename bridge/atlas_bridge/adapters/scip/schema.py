"""Field numbers of the SCIP messages the bridge reads (scip.proto, github.com/sourcegraph/scip, v0.10)."""


class IndexFields:
    DOCUMENTS = 2


class DocumentFields:
    RELATIVE_PATH = 1
    OCCURRENCES = 2


class OccurrenceFields:
    RANGE = 1  # deprecated packed [line, start char, (end line,) end char]; still what most indexers write
    SYMBOL = 2
    SYMBOL_ROLES = 3
    ENCLOSING_RANGE = 7  # packed, like RANGE: the whole definition (a function's body) around its name
    SINGLE_LINE_RANGE = 8  # the typed replacement for RANGE
    MULTI_LINE_RANGE = 9


class RangeFields:
    START_LINE = 1  # SingleLineRange.line and MultiLineRange.start_line are both field 1


class SymbolRole:
    DEFINITION = 0x1
    IMPORT = 0x2
