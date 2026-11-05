"""Python route collectors: Flask/FastAPI decorators and URL rules, and Django URLconfs."""

from .converters import FlaskPath
from .decorators import DecoratorRoutes, UrlRuleRoutes
from .django import DjangoRegex, DjangoRoutes
from .prefixed import PrefixedRoutes, RouteDeclaration
from .registrations import Registrations

__all__ = [
    'DecoratorRoutes',
    'DjangoRegex',
    'DjangoRoutes',
    'FlaskPath',
    'PrefixedRoutes',
    'Registrations',
    'RouteDeclaration',
    'UrlRuleRoutes',
]
