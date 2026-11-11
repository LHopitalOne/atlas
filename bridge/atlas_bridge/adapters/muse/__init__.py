"""Adapter out: a small chat model on OpenRouter (Meta's Muse Ember by default) as the file describer and as the
reader of the requests a file sends."""

from .chat import OpenRouterChat
from .describer import MuseDescriber
from .prompt import FilePrompt
from .reader import MuseReader
from .requests import RequestPrompt

__all__ = ['FilePrompt', 'MuseDescriber', 'MuseReader', 'OpenRouterChat', 'RequestPrompt']
