"""Route path converters: Flask `<int:id>`, `<path:rest>` and Starlette/Django `{p:path}`, `{n:int}`."""

import re


class FlaskPath:
    """Turns converter syntax into canonical path templates: '/a/<int:id>/<path:rest>' -> '/a/{id}/{*rest}'."""

    ANGLE = re.compile(r'<(?:(\w+)(?:\([^)]*\))?:)?(\w+)>')  # '<conv(args):name>'; group 1 converter, 2 name
    TYPED_PATH = re.compile(r'\{(\w+):path\}')  # '{p:path}': a tail wildcard
    TYPED = re.compile(r'\{(\w+):[^{}]*\}')  # '{n:int}': a typed parameter

    @classmethod
    def template(cls, path: str) -> str:
        s = cls.ANGLE.sub(cls._angle, path)
        s = cls.TYPED_PATH.sub(r'{*\1}', s)
        return cls.TYPED.sub(r'{\1}', s)

    @staticmethod
    def _angle(m):
        return '{*' + m.group(2) + '}' if m.group(1) == 'path' else '{' + m.group(2) + '}'
