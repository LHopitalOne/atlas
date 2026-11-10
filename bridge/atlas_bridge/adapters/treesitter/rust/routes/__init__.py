"""Routes: router builders (axum, actix-web), actix-web attribute routes, tonic gRPC services, `match`es on a
request's method and path, and their deduplication."""

from .actix_attributes import ActixAttributes
from .builders import RouterGraph
from .collectors import ActixAttributeRoutes, RouterRoutes, RustRouteCollector
from .matches import MatchRoutes
from .tonic import TonicServices
from .unique import UniqueRoutes

__all__ = [
    'ActixAttributeRoutes',
    'ActixAttributes',
    'MatchRoutes',
    'RouterGraph',
    'RouterRoutes',
    'RustRouteCollector',
    'TonicServices',
    'UniqueRoutes',
]
