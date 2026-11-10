"""Adapter out: a small chat model on OpenRouter (Meta's Muse Ember by default) as the file describer."""

from .describer import MuseDescriber
from .prompt import FilePrompt

__all__ = ['FilePrompt', 'MuseDescriber']
