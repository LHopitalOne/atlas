"""What the model is shown about one file, the shape its answer must take, and how that answer is read."""

import json
import os

from ...core.descriptions import Description
from ...usecases.ports import FileCase


class FilePrompt:
    """The file's path and the start of its code, and a JSON schema the model must answer in: one sentence of what
    the file does for the product, its role, and a few domain tags."""

    MAX_CHARS = 12_000  # the start of a file says what it is for; the rest costs tokens and says little more
    SYSTEM = (
        'You describe source files for a map of a codebase. Say what the file does for the product, concretely and '
        'in plain words. Never mention features the code does not show.'
    )
    SCHEMA = {
        'name': 'file_description',
        'strict': True,
        'schema': {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'summary': {
                    'type': 'string',
                    'description': 'One plain sentence, under 25 words: what this file does for the product',
                },
                'role': {'type': 'string', 'enum': list(Description.ROLES)},
                'tags': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': '2 to 4 lowercase words for the business domain (billing, auth, drafts...)',
                },
            },
            'required': ['summary', 'role', 'tags'],
        },
    }

    def __init__(self, folders: dict[str, str]):
        self._folders = folders

    def messages(self, case: FileCase) -> list[dict] | None:
        """The chat messages for one file, or None when it cannot be read."""
        code = self._read(case)
        if not code.strip():
            return None
        return [
            {'role': 'system', 'content': self.SYSTEM},
            {'role': 'user', 'content': f'File: {case.path}\n\n```\n{code}\n```'},
        ]

    @staticmethod
    def description(content: str | None) -> Description | None:
        """The model's JSON answer as a Description, or None when it is not one."""
        try:
            found = json.loads(content or '')
        except ValueError:
            return None
        if not isinstance(found, dict):
            return None
        tags = found.get('tags') if isinstance(found.get('tags'), list) else []
        words = tuple(str(t).strip().lower() for t in tags if str(t).strip())
        return Description(str(found.get('summary') or '').strip(), str(found.get('role') or ''), words)

    def _read(self, case):
        folder = self._folders.get(case.repo)
        if folder is None:
            return ''
        try:
            with open(os.path.join(folder, case.path), encoding='utf-8', errors='replace') as f:
                return f.read(self.MAX_CHARS)
        except OSError:
            return ''
