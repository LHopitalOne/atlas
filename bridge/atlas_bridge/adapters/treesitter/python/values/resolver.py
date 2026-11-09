"""PythonValueResolver: every expression form the Python extractor turns into URL values."""

from .calls import CallHandlers
from .helpers import HelperHandlers
from .operators import OperatorHandlers
from .scoped import ScopeResolver
from .strings import StringHandlers


class PythonValueResolver(CallHandlers, HelperHandlers, OperatorHandlers, StringHandlers, ScopeResolver):
    """Names, strings, operators, the calls that build URLs and helpers that return them, dispatched by node type
    through the kit's
    resolve(). Each handler group contributes its node types to HANDLERS."""

    HANDLERS = {
        **ScopeResolver.HANDLERS,
        **StringHandlers.HANDLERS,
        **OperatorHandlers.HANDLERS,
        **CallHandlers.HANDLERS,
    }
