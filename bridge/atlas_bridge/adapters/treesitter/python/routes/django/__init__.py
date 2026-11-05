"""Django URLconfs: module-level URL lists, include() composition, regex patterns and class-based views."""

from .collector import DjangoRoutes
from .compose import Composition, UrlComposer
from .entries import Entry, ListBinding, UrlEntries
from .lists import Contribution, UrlLists
from .regex import DjangoRegex
from .views import ViewMethods

__all__ = [
    'Composition',
    'Contribution',
    'DjangoRegex',
    'DjangoRoutes',
    'Entry',
    'ListBinding',
    'UrlComposer',
    'UrlEntries',
    'UrlLists',
    'ViewMethods',
]
