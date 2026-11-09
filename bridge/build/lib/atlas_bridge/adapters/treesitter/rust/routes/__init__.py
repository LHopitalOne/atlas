"""Routes: router builders (axum, actix-web), actix-web attribute routes, and their deduplication."""

from .actix_attributes import ActixAttributes
from .builders import RouterGraph
from .collectors import ActixAttributeRoutes, RouterRoutes, RustRouteCollector
from .unique import UniqueRoutes

__all__ = [
    'ActixAttributeRoutes',
    'ActixAttributes',
    'RouterGraph',
    'RouterRoutes',
    'RustRouteCollector',
    'UniqueRoutes',
]
